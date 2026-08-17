import { AnimatePresence, motion } from "framer-motion";
import { Circle, CircleDot, CheckCircle2, ListTodo } from "lucide-react";
import { Card, CardBody, SectionTitle } from "./ui.jsx";

const STATUS_ICON = {
  pending: <Circle className="h-4 w-4 text-ink-300" />,
  in_progress: <CircleDot className="h-4 w-4 text-brand-500 live-dot" />,
  completed: <CheckCircle2 className="h-4 w-4 text-emerald-500" />,
};

// Live view of the orchestrator's own write_todos tool -- see
// sys5_agent/agent/run_events.py. Only rendered once a generation has
// actually produced at least one todo; an empty list before that point
// isn't shown as an empty state, it just doesn't render at all (the log
// already covers "nothing has happened yet").
export default function TodoChecklist({ todos }) {
  if (!todos || todos.length === 0) return null;

  return (
    <Card>
      <CardBody>
        <SectionTitle icon={<ListTodo className="h-4 w-4 text-brand-600" />}>Plan</SectionTitle>
        <ul className="mt-2 flex flex-col gap-1.5">
          <AnimatePresence initial={false}>
            {todos.map((todo, i) => (
              <motion.li
                key={`${i}-${todo.content}`}
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                className="flex items-start gap-2 text-sm"
              >
                <span className="mt-0.5 shrink-0">{STATUS_ICON[todo.status] || STATUS_ICON.pending}</span>
                <span className={todo.status === "completed" ? "text-ink-400 line-through" : "text-ink-700"}>
                  {todo.content}
                </span>
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
      </CardBody>
    </Card>
  );
}
