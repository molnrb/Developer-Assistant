import { useEffect, useRef } from 'react'

export function useScrollToElement<T extends HTMLElement>(dependency: unknown) {
    const ref = useRef<T | null>(null)

    useEffect(() => {
        if (ref.current) {
            ref.current.scrollIntoView({ behavior: 'smooth' })
        }
    }, [dependency])

    return ref
}