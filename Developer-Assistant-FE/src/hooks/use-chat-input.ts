import {  useState } from 'react'


const useChatInput = (initialValue: string, sendUserPrompt: () => void) => {
    const [prompt, setPrompt] = useState(initialValue)



    const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (event.key === 'Enter') {
            event.preventDefault()
            if (event.shiftKey || event.ctrlKey) {
                setPrompt(prev => prev + '\n')
            } else {
                sendUserPrompt()
            }
        }
    }

    const handleChange = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
        setPrompt(event.target.value)
    }

    return {
        prompt,
        setPrompt,
        handleKeyDown,
        handleChange
    }
}

export default useChatInput
