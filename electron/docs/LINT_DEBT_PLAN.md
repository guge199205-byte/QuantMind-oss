# ESLint 存量清债计划（Electron）

## 目标

- 短期：保证新改动不再引入新的 lint 债务（增量门禁）。
- 中期：按目录分阶段将存量错误清零。
- 长期：恢复全量 `npm run lint` 作为强门禁。

## 执行顺序

1. 先启用增量门禁（CI）：
   - `npm run lint:changed`
2. 阶段一：
   - `npm run lint:phase1`
3. 阶段二：
   - `npm run lint:phase2`
4. 阶段三：
   - `npm run lint:phase3`
5. 阶段全部完成后：
   - `npm run lint`

## 阶段范围

- `phase1`：`src/pages`、`src/services`、`src/config`、`src/constants`、`src/contexts`、`src/providers`
- `phase2`：`src/features`、`src/store`、`src/stores`、`src/state`
- `phase3`：`src/components`、`src/hooks`、`src/shared`、`src/types`、`src/utils`、`src/i18n`、`src/main`、`src/monaco`

## 每日执行清单

1. 选定一个子目录（例如 `src/pages/trading`）。
2. 执行对应阶段 lint。
3. 优先修复：
   - `@typescript-eslint/no-unused-vars`
   - `@typescript-eslint/no-explicit-any`
   - `react-hooks/exhaustive-deps`
4. 提交前必须通过：
   - `npm run lint:changed`

## 验收标准

- 任意 PR：`lint:changed` 必须通过。
- 每个阶段：对应 `lint:phaseX` 全量通过。
- 最终：`npm run lint` 全量通过。
