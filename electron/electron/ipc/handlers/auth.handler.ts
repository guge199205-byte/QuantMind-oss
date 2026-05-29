import { ipcMain, IpcMainInvokeEvent } from 'electron';
import bcrypt from 'bcryptjs';

// SQLite based local auth has been removed. 
// Future implementation should use the central API service.

export function registerAuthHandlers() {
  ipcMain.handle('auth:create-user', async (event: IpcMainInvokeEvent, { username, email, password, displayName }: any) => {
    return { success: false, error: '本地离线认证已禁用，请使用远程服务' };
  });

  ipcMain.handle('auth:verify-login', async (event: IpcMainInvokeEvent, { username, password }: any) => {
    return { success: false, error: '本地离线认证已禁用，请使用远程服务' };
  });

  ipcMain.handle('auth:get-user', async (event: IpcMainInvokeEvent, { username }: any) => {
    return { success: false, error: '用户不存在' };
  });

  ipcMain.handle('auth:list-users', async () => {
    return { success: true, users: [] };
  });

  console.log('✅ Auth IPC handlers registered (Local DB Disabled)');
}
