import React from 'react';

interface Props {
  title: string;
  children: React.ReactNode;
  className?: string;
  icon?: React.ReactNode;
}

export const PanelCard: React.FC<Props> = ({ title, children, className, icon }) => (
  <div className={"panel-card " + (className || '')}>
    <div className="flex items-center gap-3 mb-4">
      {icon && <div className="text-indigo-600">{icon}</div>}
      <h3 className="panel-title mb-0">{title}</h3>
    </div>
    <div className="panel-body">{children}</div>
  </div>
);
