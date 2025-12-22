import { useState, useRef, useEffect, ReactNode, MouseEvent } from 'react'
import { createPortal } from 'react-dom'

type ContextMenuProps = {
  children: ReactNode;
  trigger: ReactNode;
  align?: 'left' | 'middle' | 'right';
};

export function ContextMenu({ children, trigger, align }: ContextMenuProps) {
  const [visible, setVisible] = useState(false)
  const [position, setPosition] = useState({ x: 0, y: 0 })
  const buttonRef = useRef<HTMLButtonElement>(null)

  const openMenu = (event: MouseEvent<HTMLButtonElement>) => {
    if (!buttonRef.current) return
    event.stopPropagation()
    const rect = buttonRef.current.getBoundingClientRect()

    setPosition({
      x: rect.left + rect.width / 2,
      y: rect.bottom + 5,
    })
    setVisible(true)
  }

  const closeMenu = () => setVisible(false)

  useEffect(() => {
    document.addEventListener('click', closeMenu)
    return () => document.removeEventListener('click', closeMenu)
  }, [])

  const transform =
    align === 'left'
      ? 'translate(-100%)'
      : align === 'right'
        ? 'translate(0)'
        : 'translate(-50%)'

  return (
    <div className="relative inline-block">
      <button
        ref={buttonRef}
        onClick={openMenu}
        className="cursor-pointer rounded-md"
      >
        {trigger}
      </button>
      {visible &&
        createPortal(
          <div
            className="absolute z-50 rounded-2xl border border-zinc-200 bg-zinc-100 p-2 shadow-lg dark:border-zinc-900 dark:bg-zinc-950 dark:text-zinc-100"
            style={{
              left: `${position.x}px`,
              top: `${position.y}px`,
              transform,
            }}
          >
            {children}
          </div>,
          document.body,
        )}
    </div>
  )
}