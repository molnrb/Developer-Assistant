import React from 'react'

type ButtonProps = {
    variant?: 'primary' | 'secondary' | 'warn' | 'danger' | 'transparent';
} & React.ButtonHTMLAttributes<HTMLButtonElement>;

export function Button({ children, variant = 'primary', className, ...props }: ButtonProps) {
    const baseStyle = 'px-4 py-2 text-zinc-100 rounded-xl text-sm font-medium transition hover:cursor-pointer shadow-md'

    const variantStyles = {
        primary: 'bg-zinc-800 hover:bg-zinc-900',
        secondary: 'bg-zinc-200 hover:bg-zinc-300 text-zinc-800 dark:bg-zinc-200 dark:text-zinc-900',
        warn: 'bg-yellow-500 hover:bg-yellow-600',
        danger: 'bg-red-600 hover:bg-red-700',
        transparent: 'text-zinc-900 dark:text-zinc-300 shadow-none border border-zinc-300 dark:border-zinc-300 hover:bg-zinc-200 dark:hover:bg-zinc-700'
    }

    return (
        <button className={`${baseStyle} ${variantStyles[variant]} ${className}`} {...props}>
            {children}
        </button>
    )
}