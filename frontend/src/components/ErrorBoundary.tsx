import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  message: string;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, message: "" };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error.message };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("ErrorBoundary caught:", error, info.componentStack);
  }

  handleReset = () => {
    this.setState({ hasError: false, message: "" });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div className="mx-auto max-w-md px-4 py-16 text-center">
          <div className="mb-4 text-4xl">⚠️</div>
          <h2 className="text-lg font-semibold">页面渲染出现问题</h2>
          <p className="mt-2 text-sm text-muted-foreground break-words">
            {this.state.message || "发生了一个未知错误"}
          </p>
          <button
            onClick={this.handleReset}
            className="mt-4 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
          >
            重新加载此部分
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
