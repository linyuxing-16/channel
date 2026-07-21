import { usePetStore } from '../stores/petStore'
import type { Config } from '../types'

/**
 * 配置管理 composable
 * 底层读写由 petStore 处理，这里提供便捷的 getter/setter
 */
export function useConfig() {
  const store = usePetStore()

  function getConfig(): Config {
    return { ...store.config }
  }

  function setConfig(partial: Partial<Config>) {
    store.updateConfig(partial)
  }

  function resetConfig() {
    import('../types').then(({ DEFAULT_CONFIG }) => {
      store.updateConfig(DEFAULT_CONFIG)
    })
  }

  return {
    config: store.config,
    getConfig,
    setConfig,
    resetConfig,
  }
}
