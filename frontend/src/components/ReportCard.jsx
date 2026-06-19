import React, { useState, useEffect } from 'react';
import './ReportCard.css';

/**
 * ReportCard – displays a selectable report type.
 */
export default function ReportCard({ type, title, description, onSelect, selected }) {
  return (
    <div
      className={`report-card ${selected ? 'selected' : ''}`}
      onClick={() => onSelect(type)}
      role="button"
      tabIndex={0}
      onKeyPress={e => { if (e.key === 'Enter') onSelect(type); }}
      style={{
        border: selected ? '2px solid #0055b3' : '1px solid #e5e7eb',
        borderRadius: 8,
        padding: '12px 16px',
        cursor: 'pointer',
        background: '#fff',
        boxShadow: '0 4px 12px rgba(0,0,0,0.05)',
        transition: 'transform 0.2s',
        transform: selected ? 'scale(1.02)' : 'scale(1)',
        margin: 8
      }}
    >
      <h3 style={{ margin: 0, fontSize: 16, color: '#111827' }}>{title}</h3>
      <p style={{ margin: '4px 0 0', fontSize: 13, color: '#6b7280' }}>{description}</p>
    </div>
  );
}
