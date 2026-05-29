import React, { useState, useEffect } from 'react';
import { HomePage } from '../pages-v2/HomePage';
import { MiningDashboardPage } from '../pages-v2/MiningDashboardPage';
import { FactorLibraryPage } from '../pages-v2/FactorLibraryPage';
import { BacktestPage } from '../pages-v2/BacktestPage';
import { SettingsPage } from '../pages-v2/SettingsPage';
import { Layout } from '../components-v2/layout/Layout';
import type { PageId } from '../components-v2/layout/Layout';
import { ParticleBackground } from '../components-v2/ParticleBackground';
import { TaskProvider, useTaskContext } from '../context-v2/TaskContext';

// Inner component to access context
const AppContent: React.FC = () => {
  const [currentPage, setCurrentPage] = useState<PageId>('home');
  const { miningTask } = useTaskContext();

  // Auto-switch to dashboard when task starts
  useEffect(() => {
    if (miningTask && miningTask.status === 'running' && currentPage === 'home') {
       // Only auto-redirect if we are on home and a new task starts
       // But wait, user requirement says: "Don't disconnect when going back to home"
       // So we should redirect to dashboard ONLY when a NEW task is created via ChatInput
       // The ChatInput in HomePage calls startMining.
       // We can detect this change.
       setCurrentPage('mining_dashboard');
    }
  }, [miningTask?.taskId]); // Only trigger on new task ID

  return (
    <>
      <ParticleBackground />
      {/*
        Use display:none to hide non-current pages instead of conditional unmounting.
        This ensures that components are not unmounted when switching pages, so WebSocket/task state is not lost.
      */}
      <div style={{ display: currentPage === 'home' ? 'block' : 'none' }}>
        <HomePage onNavigate={setCurrentPage} />
      </div>
      <div style={{ display: currentPage === 'mining_dashboard' ? 'block' : 'none' }}>
        <MiningDashboardPage onNavigate={setCurrentPage} />
      </div>
      <div style={{ display: currentPage === 'library' ? 'block' : 'none' }}>
        <Layout currentPage={currentPage} onNavigate={setCurrentPage}>
          <FactorLibraryPage />
        </Layout>
      </div>
      <div style={{ display: currentPage === 'backtest' ? 'block' : 'none' }}>
        <Layout currentPage={currentPage} onNavigate={setCurrentPage}>
          <BacktestPage />
        </Layout>
      </div>
      <div style={{ display: currentPage === 'settings' ? 'block' : 'none' }}>
        <Layout currentPage={currentPage} onNavigate={setCurrentPage}>
          <SettingsPage />
        </Layout>
      </div>
    </>
  );
};

const AppRoot: React.FC = () => {
  return (
    <TaskProvider>
      <AppContent />
    </TaskProvider>
  );
};

export default AppRoot;
export { AppRoot as App };
