import React from "react";
import Header from "../ui/dashboard/header/header";
import Sidebar from "../ui/dashboard/sidebar/sidebar";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen">
      
      {/* Sidebar: Fixed to the left */}
      <div className="w-64 bg-gray-800 text-white fixed h-full">
        <Sidebar />
      </div>

      {/* Main Content Area */}
      <div className="flex flex-col flex-1 ml-64">
        {/* Header: Sticky, with margin-top and margin-x */}
        <div className="sticky top-0 z-10 mt-4 mx-4">
          <Header />
        </div>

        {/* Main content section */}
        <main className="flex-1 p-4 bg-gray-100 overflow-y-auto mt-4 mx-4">
          {children}
        </main>
      </div>
      
    </div>
  );
}
