import React from 'react';
import { LayoutDashboard, Video, ClipboardList, Info } from 'lucide-react';

const Sidebar = ({ activeMenu, setActiveMenu }) => {
  const menuItems = [
    { id: 'Dashboard', icon: LayoutDashboard, label: 'Dashboard' },
    { id: 'Live Cam', icon: Video, label: 'Live Cam' },
    { id: 'Log Pelanggaran', icon: ClipboardList, label: 'Log Pelanggaran' },
    { id: 'Tentang Sistem', icon: Info, label: 'Tentang Sistem' },
  ];

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
      <div className="pt-6 border-t border-gray-300">
        <div className="flex items-center gap-3">
          {/* Avatar Placeholder */}
          <div className="w-10 h-10 rounded-full bg-gray-800 flex items-center justify-center text-white font-bold text-xs">
            BJ
          </div>
          <div className="overflow-hidden">
            <p className="font-bold text-sm text-gray-900 truncate">Budi Joni</p>
            <p className="text-xs text-gray-500 font-medium">Supervisor</p>
          </div>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;