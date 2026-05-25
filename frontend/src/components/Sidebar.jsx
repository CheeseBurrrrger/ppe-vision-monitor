import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { LayoutDashboard, Video, ClipboardList, Info, LogOut, ChevronUp } from 'lucide-react';

const Sidebar = ({ activeMenu, setActiveMenu }) => {
  const navigate = useNavigate();
  const [showProfile, setShowProfile] = useState(false);
  const profileRef = useRef(null);

  const username = localStorage.getItem('username') || 'User';
  const role = localStorage.getItem('role') || 'user';
  const initials = username.slice(0, 2).toUpperCase();

  const menuItems = [
    { id: 'Dashboard', icon: LayoutDashboard, label: 'Dashboard' },
    { id: 'Live Cam', icon: Video, label: 'Live Cam' },
    { id: 'Log Pelanggaran', icon: ClipboardList, label: 'Log Pelanggaran' },
    { id: 'Tentang Sistem', icon: Info, label: 'Tentang Sistem' },
  ];

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('role');
    localStorage.removeItem('username');
    navigate('/login');
  };

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (profileRef.current && !profileRef.current.contains(e.target)) {
        setShowProfile(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <aside className="w-40 lg:w-48 xl:w-56 flex-shrink-0 bg-[#F2EADA]
                  border-r border-gray-300 flex flex-col p-4 transition-all">
      {/* Logo Section */}
      <div className="mb-10">
        <h1 className="text-2xl font-bold tracking-tight text-gray-900">VisionGuard</h1>
        <div className="h-[1px] bg-gray-400 w-full my-2 opacity-50" />
        <p className="text-[10px] text-gray-500 uppercase tracking-widest font-semibold">
          K3 Monitoring <br /> PT. Epson Indonesia
        </p>
      </div>

      {/* Navigation Menu */}
      <nav className="flex-1 space-y-2">
        {menuItems.map((item) => {
          const isActive = activeMenu === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveMenu(item.id)}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 group ${
                isActive
                  ? 'bg-[#DCCFB2] text-gray-900 font-bold shadow-sm'
                  : 'text-gray-500 hover:bg-gray-200/50 hover:text-gray-700'
              }`}
            >
              <item.icon
                size={20}
                className={`${isActive ? 'text-gray-900' : 'text-gray-400 group-hover:text-gray-600'}`}
              />
              <span className="text-sm">{item.label}</span>
            </button>
          );
        })}
      </nav>

      {/* User Profile Section */}
      <div className="pt-6 border-t border-gray-300" ref={profileRef}>
        {showProfile && (
          <div className="mb-3 bg-white rounded-xl shadow-lg border border-gray-200 overflow-hidden">
            <div className="px-4 py-4 flex flex-col items-center gap-2 bg-[#F5EFE0]">
              <div className="w-14 h-14 rounded-full bg-gray-800 flex items-center justify-center text-white font-bold text-base">
                {initials}
              </div>
              <div className="text-center">
                <p className="font-bold text-sm text-gray-900">{username}</p>
                <p className="text-xs text-gray-500 capitalize">{role}</p>
              </div>
            </div>
            <div className="h-px bg-gray-100" />
            <div className="py-1">
              <button
                onClick={handleLogout}
                className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-red-500 hover:bg-red-50 transition-colors"
              >
                <LogOut size={15} className="text-red-400" />
                Log Out
              </button>
            </div>
          </div>
        )}

        <button
          onClick={() => setShowProfile((prev) => !prev)}
          className="w-full flex items-center gap-3 rounded-lg px-2 py-2 hover:bg-[#DCCFB2] transition-colors duration-150 group"
        >
          <div className="w-10 h-10 rounded-full bg-gray-800 flex items-center justify-center text-white font-bold text-xs flex-shrink-0">
            {initials}
          </div>
          <div className="overflow-hidden flex-1 text-left">
            <p className="font-bold text-sm text-gray-900 truncate">{username}</p>
            <p className="text-xs text-gray-500 font-medium capitalize">{role}</p>
          </div>
          <ChevronUp
            size={14}
            className={`text-gray-400 flex-shrink-0 transition-transform duration-200 ${showProfile ? 'rotate-180' : 'rotate-0'}`}
          />
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;
