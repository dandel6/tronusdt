'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Bell,
  User,
  Settings,
  LogOut,
  ChevronDown,
  Moon,
  Sun,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/authStore';
import { ROLE_LABELS } from '@/types';

interface Notification {
  id: string;
  title: string;
  message: string;
  time: string;
  type: 'info' | 'warning' | 'success' | 'danger';
  read: boolean;
}

interface HeaderProps {
  title?: string;
}

export function Header({ title }: HeaderProps) {
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [isNotificationOpen, setIsNotificationOpen] = useState(false);
  const { admin, logout } = useAuthStore();

  const [notifications, setNotifications] = useState<Notification[]>([
    {
      id: '1',
      title: '대량 입금 감지',
      message: '5,000 USDT 입금이 감지되었습니다.',
      time: '5분 전',
      type: 'info',
      read: false,
    },
    {
      id: '2',
      title: '출금 승인 대기',
      message: '3건의 출금 요청이 대기 중입니다.',
      time: '1시간 전',
      type: 'warning',
      read: false,
    },
    {
      id: '3',
      title: '스위핑 완료',
      message: '10건의 입금이 스위핑되었습니다.',
      time: '2시간 전',
      type: 'success',
      read: false,
    },
  ]);

  const unreadCount = notifications.filter(n => !n.read).length;

  // Function to play notification sound using Web Audio API
  const playNotificationSound = () => {
    try {
      const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
      const oscillator = audioContext.createOscillator();
      const gainNode = audioContext.createGain();

      oscillator.connect(gainNode);
      gainNode.connect(audioContext.destination);

      oscillator.frequency.setValueAtTime(880, audioContext.currentTime); // A5 note
      oscillator.frequency.setValueAtTime(1047, audioContext.currentTime + 0.1); // C6 note

      gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.3);

      oscillator.start(audioContext.currentTime);
      oscillator.stop(audioContext.currentTime + 0.3);
    } catch (e) {
      // Audio not supported, ignore
    }
  };

  // Mark all notifications as read and close
  const handleMarkAllRead = () => {
    setNotifications([]);
    setIsNotificationOpen(false);
  };

  // Add new notification (can be called from anywhere)
  const addNotification = (notification: Omit<Notification, 'id' | 'read'>) => {
    const newNotification: Notification = {
      ...notification,
      id: Date.now().toString(),
      read: false,
    };
    setNotifications(prev => [newNotification, ...prev]);
    playNotificationSound();
  };

  // Expose addNotification globally for other components to use
  useEffect(() => {
    (window as any).addNotification = addNotification;
    (window as any).playNotificationSound = playNotificationSound;
    return () => {
      delete (window as any).addNotification;
      delete (window as any).playNotificationSound;
    };
  }, []);

  const handleLogout = () => {
    logout();
    window.location.href = '/login';
  };

  return (
    <header className="sticky top-0 z-20 glass border-b border-white/5">
      <div className="flex items-center justify-between h-16 px-6">
        {/* Left Section */}
        <div className="flex items-center gap-4">
          {title && (
            <h1 className="text-xl font-semibold text-white hidden md:block">
              {title}
            </h1>
          )}
        </div>

        {/* Right Section */}
        <div className="flex items-center gap-4">
          {/* Notifications */}
          <div className="relative">
            <button
              onClick={() => setIsNotificationOpen(!isNotificationOpen)}
              className="relative p-2 rounded-xl hover:bg-white/5 transition-colors"
            >
              <Bell className="w-5 h-5 text-dark-200" />
              {unreadCount > 0 && (
                <span className="absolute top-1 right-1 w-2 h-2 bg-accent-danger rounded-full" />
              )}
            </button>

            <AnimatePresence>
              {isNotificationOpen && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 10 }}
                  className="absolute right-0 top-12 w-80 bg-dark-800 border border-white/10 rounded-2xl shadow-2xl p-4"
                >
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="font-medium text-white">알림</h3>
                    {notifications.length > 0 && (
                      <button
                        onClick={handleMarkAllRead}
                        className="text-xs text-accent-primary hover:underline"
                      >
                        모두 읽음
                      </button>
                    )}
                  </div>
                  <div className="space-y-3 max-h-80 overflow-y-auto custom-scrollbar">
                    {notifications.length === 0 ? (
                      <p className="text-sm text-dark-400 text-center py-4">
                        새로운 알림이 없습니다.
                      </p>
                    ) : (
                      notifications.map(notification => (
                        <NotificationItem
                          key={notification.id}
                          title={notification.title}
                          message={notification.message}
                          time={notification.time}
                          type={notification.type}
                        />
                      ))
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Profile Dropdown */}
          <div className="relative">
            <button
              onClick={() => setIsProfileOpen(!isProfileOpen)}
              className="flex items-center gap-2 p-2 rounded-xl hover:bg-white/5 transition-colors"
            >
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent-primary to-accent-secondary flex items-center justify-center">
                <User className="w-4 h-4 text-white" />
              </div>
              <div className="hidden md:block text-left">
                <p className="text-sm font-medium text-white">
                  {admin?.full_name || admin?.username}
                </p>
                <p className="text-xs text-dark-300">
                  {admin && ROLE_LABELS[admin.role]}
                </p>
              </div>
              <ChevronDown className="w-4 h-4 text-dark-300" />
            </button>

            <AnimatePresence>
              {isProfileOpen && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 10 }}
                  className="absolute right-0 top-14 w-56 bg-dark-800 border border-white/10 rounded-2xl shadow-2xl p-2"
                >
                  <div className="py-1">
                    <button
                      onClick={() => { setIsProfileOpen(false); window.location.href = '/profile'; }}
                      className="w-full flex items-center gap-3 px-4 py-2 text-dark-200 hover:text-white hover:bg-white/5 rounded-lg transition-colors"
                    >
                      <User className="w-4 h-4" />
                      <span className="text-sm">프로필</span>
                    </button>
                    <button
                      onClick={() => { setIsProfileOpen(false); window.location.href = '/settings'; }}
                      className="w-full flex items-center gap-3 px-4 py-2 text-dark-200 hover:text-white hover:bg-white/5 rounded-lg transition-colors"
                    >
                      <Settings className="w-4 h-4" />
                      <span className="text-sm">설정</span>
                    </button>
                    <div className="my-1 border-t border-white/5" />
                    <button
                      onClick={handleLogout}
                      className="w-full flex items-center gap-3 px-4 py-2 text-accent-danger hover:bg-accent-danger/10 transition-colors"
                    >
                      <LogOut className="w-4 h-4" />
                      <span className="text-sm">로그아웃</span>
                    </button>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </header>
  );
}

// 알림 아이템
function NotificationItem({
  title,
  message,
  time,
  type,
}: {
  title: string;
  message: string;
  time: string;
  type: 'info' | 'warning' | 'success' | 'danger';
}) {
  const colors = {
    info: 'bg-accent-info',
    warning: 'bg-accent-warning',
    success: 'bg-accent-success',
    danger: 'bg-accent-danger',
  };

  return (
    <div className="flex gap-3 p-2 rounded-lg hover:bg-white/5 cursor-pointer transition-colors">
      <div className={cn('w-2 h-2 rounded-full mt-2', colors[type])} />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-white">{title}</p>
        <p className="text-xs text-dark-300 truncate">{message}</p>
        <p className="text-xs text-dark-400 mt-1">{time}</p>
      </div>
    </div>
  );
}
