# store

用途：状态管理与数据流。

## 说明
- 归属路径：electron\src\features\user-center\store
- `profileSlice` 在拉取/更新用户档案成功后会同步回写 `localStorage.user` 的 `username/full_name/email`，避免社区等读取登录快照的区域显示旧昵称。
- 修改本目录代码后请同步更新本 README
