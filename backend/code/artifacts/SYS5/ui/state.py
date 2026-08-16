"""
The chat state machine: one step name -> one handler function, each taking
the current session dict and the user's latest input and returning
(updated session dict, bot turn dict).

`app.py` owns the actual Flask session storage; this module is pure logic
so it's testable without a running server (see `test_state.py`).

A "bot turn" is a plain JSON-able dict:
    {
        "messages": ["...", "..."],      # one or more bubbles, in order
        "kind": "text"|"textarea"|"buttons"|"checkboxes"|"none",
        "choices": [{"label", "value"}, ...],   # for buttons/checkboxes
        "placeholder": "...",             # for text/textarea
        "prefill": "...",                 # pre-filled text/textarea content
    }

Every handler is registered under a step name via `@step(...)` and is
called as `handler(session, payload) -> dict | None`:
  - Returning a bot-turn dict *and* changing `session["step"]` means "move
    to a new step, here's what it says".
  - Returning a bot-turn dict *without* changing `session["step"]` means
    "re-show this same step (usually because of a validation error) --
    `payload` didn't advance anything".
`payload` is whatever the client posted: `{"value": ...}` for a button
click, `{"selected": [...]}` for a checkbox group's "Done", or
`{"text": ...}` for free text.
"""

from __future__ import annotations

from typing import Callable, Optional

import builders as b

STEP_HANDLERS: dict[str, Callable[[dict, dict], dict]] = {}


def step(name: str):
    def register(fn):
        STEP_HANDLERS[name] = fn
        return fn

    return register


def bot(
    *messages: str,
    kind: str = "text",
    choices: Optional[list[dict]] = None,
    placeholder: str = "",
    prefill: str = "",
) -> dict:
    return {
        "messages": list(messages),
        "kind": kind,
        "choices": choices or [],
        "placeholder": placeholder,
        "prefill": prefill,
    }


def _combine(first: dict, second: dict) -> dict:
    """Concatenate two bot turns: `first`'s messages lead, `second`
    supplies the actual next input widget (kind/choices/placeholder/
    prefill). Plain dict `|` would silently drop `first`'s messages
    instead (it replaces the whole "messages" list, not concatenates it),
    so every "confirm, then show the next menu" turn goes through this."""
    return {
        "messages": [*first["messages"], *second["messages"]],
        "kind": second["kind"],
        "choices": second["choices"],
        "placeholder": second["placeholder"],
        "prefill": second["prefill"],
    }


def _goto(session: dict, next_step: str) -> None:
    session["step"] = next_step


def _draft(session: dict) -> dict:
    return session.setdefault("draft", {})


def _client(session: dict) -> str:
    return session["client"]


def start_session() -> dict:
    """Fresh session dict, used for a first page load and "switch client"."""
    return {"client": None, "step": "welcome", "draft": {}, "log": []}


def process(session: dict, payload: dict) -> dict:
    """Run one turn. Mutates `session` in place; returns the bot turn dict."""
    handler = STEP_HANDLERS.get(session.get("step") or "welcome")
    if handler is None:
        _goto(session, "welcome")
        handler = STEP_HANDLERS["welcome"]
    return handler(session, payload or {})


# ---------------------------------------------------------------------------
# Welcome / client selection
# ---------------------------------------------------------------------------


@step("welcome")
def _welcome(session: dict, payload: dict) -> dict:
    value = (payload.get("value") or "").strip()
    text = (payload.get("text") or "").strip()

    if not value and not text:
        clients = b.list_clients()
        intro = (
            "Hi! I'll help you customize how this pipeline generates SYS5 test "
            "cases for a specific project -- what this app calls a **client**. "
            "A client is a folder of extra rules, skill overrides, and custom "
            "subagents that layer on top of the standard behavior for every "
            "run of that project; a project with none of that still works "
            "fine on the defaults."
        )
        if clients:
            return bot(
                intro,
                "Pick an existing client below, or type a new name to create one.",
                kind="buttons",
                choices=[{"label": c, "value": c} for c in clients],
                placeholder="or type a new client name...",
            )
        return bot(
            intro,
            "No clients exist yet -- type a name to create the first one "
            "(letters, digits, `_`/`-`/`.` only, e.g. `acme` or `acme-bcm-v2`).",
            placeholder="new client name...",
        )

    name = value or text
    try:
        name = b.validate_client_name(name)
    except b.ValidationError as e:
        return bot(f"That name doesn't work: {e} Try again.", placeholder="client name...")

    session["client"] = name
    session["draft"] = {}
    _goto(session, "main_menu")
    return _main_menu_turn(session, created=name not in b.list_clients())


# ---------------------------------------------------------------------------
# Main menu
# ---------------------------------------------------------------------------

_MAIN_MENU_CHOICES = [
    {"label": "Add a memory rule", "value": "add_memory"},
    {"label": "Override a skill", "value": "add_skill"},
    {"label": "Add a custom subagent", "value": "add_subagent"},
    {"label": "Manage existing items", "value": "manage"},
    {"label": "Switch client", "value": "switch_client"},
    {"label": "I'm done", "value": "done"},
]


def _main_menu_turn(session: dict, created: bool = False) -> dict:
    client = _client(session)
    lines = [f"Working on **{client}**. What would you like to do?"]
    if created:
        lines.insert(0, f"Starting fresh -- **{client}** has no customizations yet.")
    lines.append(
        "- **Memory rule** -- a short standing instruction, always in effect "
        "for this client (e.g. \"Variant is always N/A for this project\").\n"
        "- **Skill override** -- replace one of the standard instruction "
        "sheets (how to write test steps, how to resolve signals, etc.) "
        "with this client's own version.\n"
        "- **Custom subagent** -- an extra specialist the orchestrator can "
        "call on for this client, alongside the six it always uses."
    )
    return bot(*lines, kind="buttons", choices=_MAIN_MENU_CHOICES)


@step("main_menu")
def _main_menu(session: dict, payload: dict) -> dict:
    value = payload.get("value")
    if value == "add_memory":
        session["draft"] = {"kind": "memory"}
        _goto(session, "memory_edit")
        return _memory_edit_turn(session)
    if value == "add_skill":
        session["draft"] = {"kind": "skill"}
        _goto(session, "skill_pick")
        return _skill_pick_turn()
    if value == "add_subagent":
        session["draft"] = {"kind": "subagent"}
        _goto(session, "subagent_name")
        return bot(
            "A subagent is a specialist the orchestrator can delegate a job "
            "to -- it gets its own separate conversation and reports back "
            "only a short summary, which is what keeps a big run from "
            "overwhelming the orchestrator's own context. What should this "
            "one be called? Use lowercase-with-hyphens, e.g. "
            "`extra-safety-checks-agent`.",
            placeholder="my-custom-agent",
        )
    if value == "manage":
        _goto(session, "manage_menu")
        return _manage_menu_turn()
    if value == "switch_client":
        session["client"] = None
        session["draft"] = {}
        _goto(session, "welcome")
        return _welcome(session, {})
    if value == "done":
        _goto(session, "end")
        return _end_turn(session)
    return _main_menu_turn(session)


@step("end")
def _end(session: dict, payload: dict) -> dict:
    _goto(session, "welcome")
    session["client"] = None
    session["draft"] = {}
    return _welcome(session, {})


def _end_turn(session: dict) -> dict:
    client = _client(session)
    log = session.get("log") or []
    lines = [f"All done for now -- **{client}**'s customizations are saved and will apply to its next run."]
    if log:
        lines.append("This session: " + "; ".join(log))
    return bot(*lines, kind="buttons", choices=[{"label": "Start over", "value": "restart"}])


# ---------------------------------------------------------------------------
# Memory rule
# ---------------------------------------------------------------------------


def _memory_edit_turn(session: dict) -> dict:
    current = b.read_client_memory(_client(session))
    intro = (
        "Memory rules are always loaded, every run, for this client -- use "
        "them for something that must always be true, not a one-off note. "
        "They're appended after the standard rules, so write it as an "
        "addition (\"For this client, X\"), not a full restatement."
    )
    if current:
        intro += " Here's the current text -- edit it, or replace it entirely."
    return bot(intro, kind="textarea", placeholder="Write the rule text...", prefill=current)


@step("memory_edit")
def _memory_edit(session: dict, payload: dict) -> dict:
    text = (payload.get("text") or "").strip()
    if not text:
        return bot("The rule can't be empty. Try again, or go back.", kind="textarea")
    _draft(session)["text"] = text
    _goto(session, "memory_preview")
    return bot(
        "Here's exactly what will be saved to this client's memory file:",
        f"> {text}",
        kind="buttons",
        choices=[
            {"label": "Save", "value": "save"},
            {"label": "Edit again", "value": "edit"},
            {"label": "Cancel", "value": "cancel"},
        ],
    )


@step("memory_preview")
def _memory_preview(session: dict, payload: dict) -> dict:
    value = payload.get("value")
    if value == "save":
        text = _draft(session)["text"]
        b.write_client_memory(_client(session), text)
        session.setdefault("log", []).append("added a memory rule")
        _goto(session, "main_menu")
        return _combine(bot("Saved.", kind="buttons", choices=[], placeholder=""), _main_menu_turn(session))
    if value == "edit":
        _goto(session, "memory_edit")
        return _memory_edit_turn(session)
    _goto(session, "main_menu")
    return _main_menu_turn(session)


# ---------------------------------------------------------------------------
# Skill override
# ---------------------------------------------------------------------------


def _skill_pick_turn() -> dict:
    lines = ["Which skill do you want to override for this client?"]
    for name, desc in b.OVERRIDABLE_SKILLS.items():
        lines.append(f"- **{name}** -- {desc}")
    return bot(
        *lines,
        kind="buttons",
        choices=[{"label": name, "value": name} for name in b.OVERRIDABLE_SKILLS],
    )


@step("skill_pick")
def _skill_pick(session: dict, payload: dict) -> dict:
    name = payload.get("value")
    if name not in b.OVERRIDABLE_SKILLS:
        return _skill_pick_turn()
    _draft(session)["skill_name"] = name
    if name == "domain-knowledge":
        _goto(session, "skill_domain_confirm")
        return bot(
            "Careful with this one: a client-level domain-knowledge override "
            "*replaces* the standard domain's knowledge for this client, it "
            "doesn't add to it. If you just want to add a note on top of the "
            "existing knowledge, a memory rule is usually a better fit.",
            kind="buttons",
            choices=[
                {"label": "Continue with the override", "value": "continue"},
                {"label": "Use a memory rule instead", "value": "memory_instead"},
            ],
        )
    desc, prefill = b.read_skill_starting_point(name)
    _draft(session)["prefill_description"] = desc
    _draft(session)["prefill_body"] = prefill
    _goto(session, "skill_description")
    return _skill_description_turn(session)


@step("skill_domain_confirm")
def _skill_domain_confirm(session: dict, payload: dict) -> dict:
    value = payload.get("value")
    if value == "memory_instead":
        session["draft"] = {"kind": "memory"}
        _goto(session, "memory_edit")
        return _memory_edit_turn(session)
    if value == "continue":
        _goto(session, "skill_domain_pick")
        return bot(
            "Which domain's current knowledge should this start from?",
            kind="buttons",
            choices=[
                {"label": b.settings.DOMAIN_LABELS.get(d, d), "value": d} for d in b.settings.DOMAINS
            ],
        )
    return _skill_domain_confirm(session, {})


@step("skill_domain_pick")
def _skill_domain_pick(session: dict, payload: dict) -> dict:
    domain = payload.get("value")
    if domain not in b.settings.DOMAINS:
        return bot(
            "Pick one of the listed domains.",
            kind="buttons",
            choices=[{"label": b.settings.DOMAIN_LABELS.get(d, d), "value": d} for d in b.settings.DOMAINS],
        )
    desc, prefill = b.read_skill_starting_point("domain-knowledge", domain)
    _draft(session)["prefill_description"] = desc
    _draft(session)["prefill_body"] = prefill
    _goto(session, "skill_description")
    return _skill_description_turn(session)


def _skill_description_turn(session: dict) -> dict:
    existing = b.read_client_skill_override(_client(session), _draft(session)["skill_name"])
    prefill = existing[0] if existing else _draft(session).get("prefill_description", "")
    return bot(
        "One sentence: what does this skill cover, and when should the "
        "model read it? This is the trigger text the model uses to decide "
        "whether it's relevant right now.",
        kind="text",
        placeholder="Describe when to use this skill...",
        prefill=prefill,
    )


@step("skill_description")
def _skill_description(session: dict, payload: dict) -> dict:
    text = (payload.get("text") or "").strip()
    if not text:
        return bot("Needs a description. Try again.", kind="text")
    _draft(session)["description"] = text
    _goto(session, "skill_body")
    existing = b.read_client_skill_override(_client(session), _draft(session)["skill_name"])
    prefill = existing[1] if existing else _draft(session).get("prefill_body", "")
    return bot(
        "Now the actual instructions, as Markdown -- this fully replaces "
        "the standard content for this client, so make sure it's complete, "
        "not just a diff. Starting point below; edit it or replace it.",
        kind="textarea",
        placeholder="Write the skill's instructions...",
        prefill=prefill,
    )


@step("skill_body")
def _skill_body(session: dict, payload: dict) -> dict:
    text = (payload.get("text") or "").strip()
    if not text:
        return bot("Needs some content. Try again.", kind="textarea")
    _draft(session)["body"] = text
    _goto(session, "skill_preview")
    return _skill_preview_turn(session)


def _skill_preview_turn(session: dict) -> dict:
    d = _draft(session)
    content = f"---\nname: {d['skill_name']}\ndescription: {d['description']}\n---\n\n{d['body']}"
    return bot(
        f"Here's the exact `{d['skill_name']}/SKILL.md` this client will get:",
        f"```\n{content}\n```",
        kind="buttons",
        choices=[
            {"label": "Save", "value": "save"},
            {"label": "Edit again", "value": "edit"},
            {"label": "Cancel", "value": "cancel"},
        ],
    )


@step("skill_preview")
def _skill_preview(session: dict, payload: dict) -> dict:
    value = payload.get("value")
    d = _draft(session)
    if value == "save":
        try:
            b.write_skill_override(_client(session), d["skill_name"], d["description"], d["body"])
        except b.ValidationError as e:
            _goto(session, "main_menu")
            return _combine(bot(f"Couldn't save that: {e}"), _main_menu_turn(session))
        session.setdefault("log", []).append(f"overrode the {d['skill_name']} skill")
        _goto(session, "main_menu")
        return _combine(bot(f"Saved `{d['skill_name']}` for this client."), _main_menu_turn(session))
    if value == "edit":
        _goto(session, "skill_description")
        return _skill_description_turn(session)
    _goto(session, "main_menu")
    return _main_menu_turn(session)


# ---------------------------------------------------------------------------
# Custom subagent
# ---------------------------------------------------------------------------


@step("subagent_name")
def _subagent_name(session: dict, payload: dict) -> dict:
    text = (payload.get("text") or "").strip()
    if not text:
        return bot("Needs a name. Try again.", placeholder="my-custom-agent")
    try:
        name = b.validate_subagent_name(text)
    except b.ValidationError as e:
        return bot(f"That name doesn't work: {e} Try again.", placeholder="my-custom-agent")

    d = _draft(session)
    d["name"] = name
    existing = b.read_custom_subagent(_client(session), name)
    if existing:
        d["description"] = existing.description
        d["prompt_body"] = existing.prompt_body
        d["tools"] = existing.tools
        d["skills"] = existing.skills
        prefix = f"`{name}` already exists for this client -- editing it. "
    else:
        prefix = ""
    _goto(session, "subagent_description")
    return bot(
        prefix + "One or two sentences: what does this subagent do, and when "
        "should the orchestrator call it? This is the only thing the "
        "orchestrator sees when deciding whether it's relevant.",
        kind="text",
        placeholder="Describe what this subagent does and when to use it...",
        prefill=d.get("description", ""),
    )


@step("subagent_description")
def _subagent_description(session: dict, payload: dict) -> dict:
    text = (payload.get("text") or "").strip()
    if not text:
        return bot("Needs a description. Try again.", kind="text")
    _draft(session)["description"] = text
    _goto(session, "subagent_prompt")
    d = _draft(session)
    starter = d.get("prompt_body") or (
        "Explain step by step what this subagent should do, which files in "
        "the run workspace it should read, and what it should write back. "
        "The standard output-format rules (13 columns, TC_SYS_ IDs, the "
        "=/== SET/VERIFY syntax) are appended automatically -- you don't "
        "need to repeat them here."
    )
    return bot(
        "Now its system prompt -- its own instructions, as Markdown. This "
        "is everything it knows about its job.",
        kind="textarea",
        placeholder="Write its instructions...",
        prefill=starter,
    )


@step("subagent_prompt")
def _subagent_prompt(session: dict, payload: dict) -> dict:
    text = (payload.get("text") or "").strip()
    if not text:
        return bot("Needs some instructions. Try again.", kind="textarea")
    _draft(session)["prompt_body"] = text
    _goto(session, "subagent_tools")
    return _subagent_tools_turn(session)


def _subagent_tools_turn(session: dict) -> dict:
    tools = b.available_tools()
    selected = set(_draft(session).get("tools", []))
    lines = ["Which tools can it use to read the client's workbooks? Pick any (or none, if it only reasons over files other subagents already wrote)."]
    for name, desc in tools.items():
        lines.append(f"- **{name}** -- {desc}")
    return bot(
        *lines,
        kind="checkboxes",
        choices=[{"label": name, "value": name, "checked": name in selected} for name in tools],
    )


@step("subagent_tools")
def _subagent_tools(session: dict, payload: dict) -> dict:
    selected = payload.get("selected")
    if selected is None:
        return _subagent_tools_turn(session)
    valid = set(b.available_tools())
    _draft(session)["tools"] = [t for t in selected if t in valid]
    _goto(session, "subagent_skills")
    return _subagent_skills_turn(session)


def _subagent_skills_turn(session: dict) -> dict:
    names = b.known_skill_names(_client(session))
    selected = set(_draft(session).get("skills", []))
    lines = ["Which skills should it have access to?"]
    for name in names:
        desc = b.OVERRIDABLE_SKILLS.get(name, "This client's own custom skill.")
        lines.append(f"- **{name}** -- {desc}")
    return bot(
        *lines,
        kind="checkboxes",
        choices=[{"label": name, "value": name, "checked": name in selected} for name in names],
    )


@step("subagent_skills")
def _subagent_skills(session: dict, payload: dict) -> dict:
    selected = payload.get("selected")
    if selected is None:
        return _subagent_skills_turn(session)
    valid = set(b.known_skill_names(_client(session)))
    _draft(session)["skills"] = [s for s in selected if s in valid]
    _goto(session, "subagent_preview")
    return _subagent_preview_turn(session)


def _subagent_preview_turn(session: dict) -> dict:
    d = _draft(session)
    tools_yaml = "[" + ", ".join(d.get("tools", [])) + "]"
    skills_yaml = "[" + ", ".join(d.get("skills", [])) + "]"
    content = (
        f"---\nname: {d['name']}\ndescription: {d['description']}\n"
        f"tools: {tools_yaml}\nskills: {skills_yaml}\n---\n\n{d['prompt_body']}"
    )
    return bot(
        f"Here's the exact `{d['name']}.md` this client will get (the "
        "output-contract reminder is added automatically when a run loads "
        "it, so it isn't shown here):",
        f"```\n{content}\n```",
        kind="buttons",
        choices=[
            {"label": "Save", "value": "save"},
            {"label": "Edit again", "value": "edit"},
            {"label": "Cancel", "value": "cancel"},
        ],
    )


@step("subagent_preview")
def _subagent_preview(session: dict, payload: dict) -> dict:
    value = payload.get("value")
    d = _draft(session)
    if value == "save":
        draft = b.SubagentDraft(
            name=d["name"],
            description=d["description"],
            prompt_body=d["prompt_body"],
            tools=d.get("tools", []),
            skills=d.get("skills", []),
        )
        try:
            b.write_custom_subagent(_client(session), draft)
        except b.ValidationError as e:
            _goto(session, "main_menu")
            return _combine(bot(f"Couldn't save that: {e}"), _main_menu_turn(session))
        session.setdefault("log", []).append(f"added the {d['name']} subagent")
        _goto(session, "main_menu")
        return _combine(bot(f"Saved `{d['name']}`."), _main_menu_turn(session))
    if value == "edit":
        _goto(session, "subagent_description")
        return _subagent_description_reentry(session)
    _goto(session, "main_menu")
    return _main_menu_turn(session)


def _subagent_description_reentry(session: dict) -> dict:
    d = _draft(session)
    return bot(
        "One or two sentences: what does this subagent do, and when "
        "should the orchestrator call it?",
        kind="text",
        placeholder="Describe what this subagent does and when to use it...",
        prefill=d.get("description", ""),
    )


# ---------------------------------------------------------------------------
# Manage (edit/delete existing items)
# ---------------------------------------------------------------------------

_MANAGE_MENU_CHOICES = [
    {"label": "Memory rule", "value": "memory"},
    {"label": "Skill overrides", "value": "skills"},
    {"label": "Custom subagents", "value": "subagents"},
    {"label": "Back", "value": "back"},
]


def _manage_menu_turn() -> dict:
    return bot("What do you want to review or change?", kind="buttons", choices=_MANAGE_MENU_CHOICES)


@step("manage_menu")
def _manage_menu(session: dict, payload: dict) -> dict:
    value = payload.get("value")
    client = _client(session)
    if value == "memory":
        current = b.read_client_memory(client)
        if not current:
            return _combine(bot("No memory rule for this client yet."), _manage_menu_turn())
        _goto(session, "manage_memory")
        return bot(
            f"Current memory rule:\n> {current}",
            kind="buttons",
            choices=[
                {"label": "Edit", "value": "edit"},
                {"label": "Delete", "value": "delete"},
                {"label": "Back", "value": "back"},
            ],
        )
    if value == "skills":
        overrides = b.list_client_skill_overrides(client)
        if not overrides:
            return _combine(bot("No skill overrides for this client yet."), _manage_menu_turn())
        _goto(session, "manage_skills_list")
        return bot(
            "Which skill override?",
            kind="buttons",
            choices=[{"label": name, "value": name} for name in overrides] + [{"label": "Back", "value": "back"}],
        )
    if value == "subagents":
        subs = b.list_custom_subagents(client)
        if not subs:
            return _combine(bot("No custom subagents for this client yet."), _manage_menu_turn())
        _goto(session, "manage_subagents_list")
        return bot(
            "Which subagent?",
            kind="buttons",
            choices=[{"label": s["name"], "value": s["name"]} for s in subs] + [{"label": "Back", "value": "back"}],
        )
    _goto(session, "main_menu")
    return _main_menu_turn(session)


@step("manage_memory")
def _manage_memory(session: dict, payload: dict) -> dict:
    value = payload.get("value")
    if value == "edit":
        session["draft"] = {"kind": "memory"}
        _goto(session, "memory_edit")
        return _memory_edit_turn(session)
    if value == "delete":
        _goto(session, "manage_memory_confirm_delete")
        return bot(
            "Delete this client's memory rule?",
            kind="buttons",
            choices=[{"label": "Yes, delete", "value": "yes"}, {"label": "No, keep it", "value": "no"}],
        )
    _goto(session, "manage_menu")
    return _manage_menu_turn()


@step("manage_memory_confirm_delete")
def _manage_memory_confirm_delete(session: dict, payload: dict) -> dict:
    if payload.get("value") == "yes":
        b.delete_client_memory(_client(session))
        session.setdefault("log", []).append("removed the memory rule")
        _goto(session, "main_menu")
        return _combine(bot("Deleted."), _main_menu_turn(session))
    _goto(session, "main_menu")
    return _main_menu_turn(session)


@step("manage_skills_list")
def _manage_skills_list(session: dict, payload: dict) -> dict:
    value = payload.get("value")
    if value == "back" or value is None:
        _goto(session, "manage_menu")
        return _manage_menu_turn()
    if value not in b.list_client_skill_overrides(_client(session)):
        _goto(session, "manage_menu")
        return _manage_menu_turn()
    _draft(session)["skill_name"] = value
    _goto(session, "manage_skill_detail")
    desc, body = b.read_client_skill_override(_client(session), value) or ("", "")
    return bot(
        f"**{value}** -- {desc}\n\n```\n{body}\n```",
        kind="buttons",
        choices=[
            {"label": "Edit", "value": "edit"},
            {"label": "Delete", "value": "delete"},
            {"label": "Back", "value": "back"},
        ],
    )


@step("manage_skill_detail")
def _manage_skill_detail(session: dict, payload: dict) -> dict:
    value = payload.get("value")
    skill_name = _draft(session)["skill_name"]
    if value == "edit":
        session["draft"] = {"kind": "skill", "skill_name": skill_name}
        _goto(session, "skill_description")
        return _skill_description_turn(session)
    if value == "delete":
        _goto(session, "manage_skill_confirm_delete")
        return bot(
            f"Delete the `{skill_name}` override? This client will fall back to the standard version.",
            kind="buttons",
            choices=[{"label": "Yes, delete", "value": "yes"}, {"label": "No, keep it", "value": "no"}],
        )
    _goto(session, "manage_skills_list")
    return _manage_menu_turn()


@step("manage_skill_confirm_delete")
def _manage_skill_confirm_delete(session: dict, payload: dict) -> dict:
    if payload.get("value") == "yes":
        skill_name = _draft(session)["skill_name"]
        b.delete_skill_override(_client(session), skill_name)
        session.setdefault("log", []).append(f"removed the {skill_name} override")
        _goto(session, "main_menu")
        return _combine(bot("Deleted."), _main_menu_turn(session))
    _goto(session, "main_menu")
    return _main_menu_turn(session)


@step("manage_subagents_list")
def _manage_subagents_list(session: dict, payload: dict) -> dict:
    value = payload.get("value")
    names = [s["name"] for s in b.list_custom_subagents(_client(session))]
    if value == "back" or value is None:
        _goto(session, "manage_menu")
        return _manage_menu_turn()
    if value not in names:
        _goto(session, "manage_menu")
        return _manage_menu_turn()
    _draft(session)["subagent_name"] = value
    _goto(session, "manage_subagent_detail")
    d = b.read_custom_subagent(_client(session), value)
    return bot(
        f"**{value}** -- {d.description}\n\nTools: {', '.join(d.tools) or '(none)'}\n"
        f"Skills: {', '.join(d.skills) or '(none)'}\n\n```\n{d.prompt_body}\n```",
        kind="buttons",
        choices=[
            {"label": "Edit", "value": "edit"},
            {"label": "Delete", "value": "delete"},
            {"label": "Back", "value": "back"},
        ],
    )


@step("manage_subagent_detail")
def _manage_subagent_detail(session: dict, payload: dict) -> dict:
    value = payload.get("value")
    name = _draft(session)["subagent_name"]
    if value == "edit":
        d = b.read_custom_subagent(_client(session), name)
        session["draft"] = {
            "kind": "subagent",
            "name": name,
            "description": d.description,
            "prompt_body": d.prompt_body,
            "tools": d.tools,
            "skills": d.skills,
        }
        _goto(session, "subagent_description")
        return _subagent_description_reentry(session)
    if value == "delete":
        _goto(session, "manage_subagent_confirm_delete")
        return bot(
            f"Delete `{name}`?",
            kind="buttons",
            choices=[{"label": "Yes, delete", "value": "yes"}, {"label": "No, keep it", "value": "no"}],
        )
    _goto(session, "manage_subagents_list")
    return _manage_menu_turn()


@step("manage_subagent_confirm_delete")
def _manage_subagent_confirm_delete(session: dict, payload: dict) -> dict:
    if payload.get("value") == "yes":
        name = _draft(session)["subagent_name"]
        b.delete_custom_subagent(_client(session), name)
        session.setdefault("log", []).append(f"removed the {name} subagent")
        _goto(session, "main_menu")
        return _combine(bot("Deleted."), _main_menu_turn(session))
    _goto(session, "main_menu")
    return _main_menu_turn(session)
