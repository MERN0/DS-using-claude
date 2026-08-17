import { Component } from "react";
import { AlertTriangle, RotateCcw } from "lucide-react";
import { Button } from "./ui.jsx";

// Catches render-time errors anywhere in the tree below it so a single
// broken panel doesn't take down the whole dashboard with a blank page --
// there was previously no error boundary at all, so any uncaught render
// error left the user staring at nothing with no way to recover short of a
// manual refresh.
export class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error("Unhandled UI error:", error, info);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="flex min-h-screen items-center justify-center p-6">
        <div className="max-w-sm text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-rose-100 text-rose-600">
            <AlertTriangle className="h-6 w-6" />
          </div>
          <h1 className="text-[15px] font-semibold text-ink-900">Something went wrong</h1>
          <p className="mt-1.5 text-sm text-ink-500">
            {this.state.error.message || "An unexpected error occurred."}
          </p>
          <Button
            tone="primary"
            className="mt-4"
            icon={<RotateCcw className="h-4 w-4" />}
            onClick={() => this.setState({ error: null })}
          >
            Try again
          </Button>
        </div>
      </div>
    );
  }
}
