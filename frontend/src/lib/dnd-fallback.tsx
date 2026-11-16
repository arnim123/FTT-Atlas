/** Offline adapter. Vite uses the real @dnd-kit/core automatically when installed. */
import { createContext, useContext, useCallback, useState, useRef, type ReactNode, type DragEvent, type KeyboardEvent } from 'react';
type Item = {
  id: string | number;
  data: {
    current: Record<string, unknown>;
  };
};
export interface DragEndEvent {
  active: Item;
  over: Item | null;
}
export interface DragStartEvent {
  active: Item;
}
type State = {
  active: Item | null;
  over: string | number | null;
  start: (item: Item) => void;
  hover: (id: string | number | null) => void;
  end: (id: string | number | null) => void;
};
const Context = createContext<State | null>(null);
export class PointerSensor {
}
export class KeyboardSensor {
}
export const pointerWithin = () => [];
export const closestCenter = () => [];
export const useSensor = (sensor: unknown, options?: unknown) => ({ sensor, options });
export const useSensors = (...sensors: unknown[]) => sensors;
export function DndContext({ children, onDragStart, onDragEnd, onDragCancel }: {
  children: ReactNode;
  sensors?: unknown;
  collisionDetection?: unknown;
  onDragStart?: (event: DragStartEvent) => void;
  onDragEnd?: (event: DragEndEvent) => void;
  onDragCancel?: () => void;
}) {
  const [active, setActive] = useState<Item | null>(null);
  const [over, hover] = useState<string | number | null>(null);
  const activeRef = useRef<Item | null>(null);
  const start = (item: Item) => { activeRef.current = item; setActive(item); onDragStart?.({ active: item }); };
  const end = (id: string | number | null) => {
    const item = activeRef.current; activeRef.current = null; setActive(null); hover(null); if (item)
      onDragEnd?.({ active: item, over: id === null ? null : { id, data: { current: {} } } });
  };
  function keyboard(event: KeyboardEvent) {
    if (!activeRef.current)
      return; if (event.key === 'Escape') {
        event.preventDefault();
        activeRef.current = null;
        setActive(null);
        hover(null);
        onDragCancel?.();
      } if (event.key === 'Enter') {
        const target = (event.target as HTMLElement).closest<HTMLElement>('[data-drop-id]');
        if (target) {
          event.preventDefault();
          event.stopPropagation();
          end(target.dataset.dropId!);
        }
      }
  }
  return <Context.Provider value={{ active, over, start, hover, end }}>
    <div onKeyDownCapture={keyboard}>{children}</div>
    <span className="sr-only" role="status">{active ? 'Item picked up. Tab to a destination folder and press Enter to move. Press Escape to cancel.' : ''}</span>
  </Context.Provider>;
}
export function useDraggable({ id, data = {}, disabled }: {
  id: string | number;
  data?: Record<string, unknown>;
  disabled?: boolean;
}) {
  const context = useContext(Context);
  const node = useRef<HTMLElement | null>(null);
  const listeners = disabled || !context ? {} : {
    onDragStart: (event: DragEvent) => { event.stopPropagation(); event.dataTransfer.effectAllowed = 'move'; event.dataTransfer.setData('text/plain', String(id)); context.start({ id, data: { current: data } }); }, onDragEnd: () => context.end(null), onKeyDown: (event: KeyboardEvent) => {
      if (event.code === 'Space') {
        event.preventDefault();
        context.start({ id, data: { current: data } });
      }
    }
  };
  return { setNodeRef: useCallback((element: HTMLElement | null) => { node.current = element; }, []), attributes: { draggable: !disabled, tabIndex: disabled ? -1 : 0, role: 'button' as const, 'aria-roledescription': 'draggable item' }, listeners, isDragging: context?.active?.id === id, transform: null };
}
export function useDroppable({ id, disabled }: {
  id: string | number;
  disabled?: boolean;
}) {
  const context = useContext(Context);
  const cleanup = useRef<() => void>();
  const setNodeRef = useCallback((element: HTMLElement | null) => {
    cleanup.current?.();
    if (!element || disabled || !context)
      return;
    element.dataset.dropId = String(id);
    const over = (event: globalThis.DragEvent) => {
      if (!context.active)
        return; event.preventDefault(); event.stopPropagation(); context.hover(id);
    };
    const leave = (event: globalThis.DragEvent) => {
      if (!element.contains(event.relatedTarget as Node))
        context.hover(null);
    };
    const drop = (event: globalThis.DragEvent) => { event.preventDefault(); event.stopPropagation(); context.end(id); };
    element.addEventListener('dragover', over);
    element.addEventListener('dragleave', leave);
    element.addEventListener('drop', drop);
    cleanup.current = () => { delete element.dataset.dropId; element.removeEventListener('dragover', over); element.removeEventListener('dragleave', leave); element.removeEventListener('drop', drop); };
  }, [context, disabled, id]);
  return { setNodeRef, isOver: context?.over === id };
}
export function DragOverlay({ children }: {
  children: ReactNode;
}) { return <div className="pointer-events-none fixed bottom-16 right-5 z-40">{children}</div>; }
