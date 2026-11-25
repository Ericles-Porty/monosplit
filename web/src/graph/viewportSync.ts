/** Shares zoom and pan between graph panes that use the same node positions. */
export interface Viewport {
  zoom: number;
  pan: { x: number; y: number };
}

export class ViewportSync {
  private listeners = new Map<string, (viewport: Viewport) => void>();

  subscribe(id: string, apply: (viewport: Viewport) => void): () => void {
    this.listeners.set(id, apply);
    return () => {
      this.listeners.delete(id);
    };
  }

  publish(source: string, viewport: Viewport): void {
    for (const [id, apply] of this.listeners) if (id !== source) apply(viewport);
  }
}
