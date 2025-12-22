type ContextMenuItemProps = {
  children: React.ReactNode;
  onClick?: () => void;
  className?: string;
}

export function ContextMenuItem({ children, onClick, className }: ContextMenuItemProps) {
  return (
    <div
      onClick={onClick}
      className={`flex w-full not-last:shadow-2xs cursor-pointer gap-2 rounded-md p-3 text-sm hover:bg-zinc-200 dark:hover:bg-zinc-800 ${className}`}
    >
      {children}
    </div>
  )
}