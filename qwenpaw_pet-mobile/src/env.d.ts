/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}

// pixi-live2d-display 类型声明
declare module 'pixi-live2d-display' {
  import * as PIXI from 'pixi.js'

  export class Live2DModel extends PIXI.Container {
    static from(modelPath: string): Promise<Live2DModel>
    motion(name: string, index?: number): Promise<void>
    expression(name: string): Promise<void>
    readonly internalModel: any
    focus(x: number, y: number): void
    focusOn(x: number, y: number, motion?: boolean): void
    lipSync: boolean
    lipSyncValue: number
  }

  export function initCDN(lib: any): void
}

// Live2D Cubism Core 声明
interface Window {
  Live2DCubismCore: any
}
