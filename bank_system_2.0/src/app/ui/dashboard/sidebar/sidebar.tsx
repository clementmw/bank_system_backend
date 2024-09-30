// src/app/dashboard/components/Sidebar.tsx
import Link from "next/link";
import { CiLogout, CiUser } from "react-icons/ci";
import { MdOutlineContactSupport, MdAccountBalance } from "react-icons/md";
import { FaHistory } from "react-icons/fa";
import { FaArrowRightArrowLeft } from "react-icons/fa6";
import { GiPayMoney } from "react-icons/gi";
import Image from 'next/image';

export default function Sidebar() {
  const menuItems = [
    {
      title: "Accounts",
      list: [
        {
          name: "Overview",
          path: "/dashboard/account",
          icon: <MdAccountBalance />,
        },
        {
          name: "Create",
          path: "/dashboard/balance",
          icon: <GiPayMoney />,
        },
      ],
    },
    {
      title: "Transact",
      list: [
        {
          name: "Transact",
          path: "/dashboard/transact",
          icon: <FaArrowRightArrowLeft />,
        },
        {
          name: "Transaction History",
          path: "/dashboard/transaction",
          icon: <FaHistory />,
        },
      ],
    },
    {
      title: "Profile",
      list: [
        {
          name: "View Profile",
          path: "/dashboard/profile",
          icon: <CiUser />,
        },
      ],
    },
    {
      title: "Support",
      list: [
        {
          name: "Support",
          path: "/dashboard/support",
          icon: <MdOutlineContactSupport />,
        },
      ],
    },
    {
      title: "Logout",
      list: [
        {
          name: "Logout",
          path: "/dashboard/logout",
          icon: <CiLogout />,
        },
      ],
    },
  ];

  return (
    <div className="w-64 h-full  text-white flex flex-col">
      {/* User Info */}
      <div className="flex items-center justify-center mt-6 mb-10">
        <div className="text-center">
          <Image
            className="rounded-full border-2 border-gray-300"
            src="/default-profile.png" // Add default image or dynamic src when backend is integrated
            width={50}
            height={50}
            alt="User profile"
          />
          <p className="mt-2 text-sm">Username</p> {/* Placeholder, replace with dynamic username */}
        </div>
      </div>

      {/* Menu Items */}
      <ul className="flex-1 px-4 space-y-4">
        {menuItems.map((section) => (
          <li key={section.title}>
            <h4 className="text-sm uppercase text-gray-400 mb-2">{section.title}</h4>
            <ul>
              {section.list.map((item) => (
                <li key={item.name} className="mb-2">
                  <Link href={item.path} className="flex items-center p-2 rounded-lg hover:bg-gray-700">
                    <span className="text-lg mr-4">{item.icon}</span>
                    <span className="text-sm">{item.name}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>

      {/* Footer (Logout button could go here if needed) */}
    </div>
  );
}
