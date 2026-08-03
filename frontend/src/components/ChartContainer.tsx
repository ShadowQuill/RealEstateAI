import {
  cloneElement, useEffect, useRef, useState, type ReactElement,
} from "react";

interface Props {
  height: number;
  children: ReactElement<Record<string, unknown>>;
  /** 当容器有真实宽高时才渲染图表，避免 recharts 在 0 尺寸下崩溃 */
  className?: string;
  /** 数据变化时强制重建图表实例，避免就地复用导致的 DOM 冲突 */
  resetKey?: string | number;
}

/**
 * recharts 2.x 在 React 19 下，ResponsiveContainer 内部的 ResizeObserver
 * 会在提交阶段与 React 19 的 DOM 操作冲突，引发 insertBefore/removeChild 崩溃。
 *
 * 根治办法：完全不用 ResponsiveContainer，而是用 ResizeObserver 测量出具体像素宽高，
 * 直接把 width/height 作为 props 注入到图表组件（BarChart/ScatterChart/ComposedChart 等），
 * 这样 recharts 不再自行操作 DOM 尺寸，从根上规避该 bug。
 */
export function ChartContainer({ height, children, className, resetKey }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () => setWidth(el.clientWidth);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={ref} className={className} style={{ width: "100%", height }}>
      {width > 0 ? (
        cloneElement(children, { width, height, key: resetKey } as Record<string, unknown>)
      ) : null}
    </div>
  );
}

export default ChartContainer;
