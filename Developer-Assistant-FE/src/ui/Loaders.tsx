

function Spinner() {
  return <div className={'flex items-center justify-center'}>
    <div className="w-6 h-6 border-4 border-zinc-800 dark:border-zinc-100 border-t-transparent rounded-full animate-spin" />
  </div>
}

function Dots() {
  return <div className={'flex items-center justify-center space-x-2'}>
    {[0, 250, 500].map((delay) => (
      <div
        key={delay}
        className={'w-2 h-2 bg-zinc-800 rounded-full dark:bg-zinc-100 animate-bounce'}
        style={{ animationDelay: `${delay}ms` }}
      />
    ))}
  </div>
}

function ChatPendingLoader() {
  return <div className="flex items-center m-4 gap-2">
    <Dots />
  </div>
}

export { Spinner, Dots, ChatPendingLoader }