import { create } from 'zustand'

type UIState = {
  isSandboxMode: boolean,
};

type UIStateActions = {
  setIsSandboxMode: (sandbox: boolean) => void,
}

type UIStateStore = UIState & UIStateActions;

const useUIStateStore = create<UIStateStore>((set) => ({
  isSandboxMode: false,
  setIsSandboxMode: (sandbox) => {
    set({ isSandboxMode: sandbox })
  },
}))

export default useUIStateStore