import { Component, type ErrorInfo, type ReactNode } from 'react';
import { Button } from '@/components/ui/button';
export class ErrorBoundary extends Component<{
  children: ReactNode;
}, {
  hasError: boolean;
}> {
  state = { hasError: false };
  static getDerivedStateFromError() { return { hasError: true }; }
  componentDidCatch(_error: Error, _info: ErrorInfo) { }
  render() {
    if (this.state.hasError)
      return <div role="alert" className="mx-auto flex min-h-screen max-w-md flex-col items-center justify-center p-8 text-center">
        <h1 className="text-2xl font-semibold">Let’s get you back on track.</h1>
        <p className="my-5 text-sm leading-relaxed text-muted-foreground">Something unexpected happened. Reload the workspace to continue.</p>
        <Button onClick={() => window.location.reload()}>Reload workspace</Button>
      </div>; return this.props.children;
  }
}
