'use client'

import React from 'react';
import { AdminProvider } from '@/contexts/admin-context';

interface AdminProviderWrapperProps {
  children: React.ReactNode;
}

export default function AdminProviderWrapper({ children }: AdminProviderWrapperProps) {
  return (
    <AdminProvider>
      {children}
    </AdminProvider>
  );
}
