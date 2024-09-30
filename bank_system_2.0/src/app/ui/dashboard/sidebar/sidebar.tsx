// src/app/dashboard/components/Sidebar.tsx
import styles from "./sidebar.module.css";
import Link from "next/link"; // Use Link for internal navigation

export default function Sidebar() {
  const menuItems = [
    {
      title: "Accounts",
      list: [
        { name: "Overview", path: "/dashboard/account" }, // Link to account page
      ],
    },
    {
      title: "Transact",
      list: [
        { name: "New Transaction",
          path: "/dashboard/transact" 
        },
        { name: "Transaction History",
            path: "/dashboard/transaction" 
        },
      ],
    },
    {
      title: "Profile",
      list: [
        { name: "View Profile",
          path: "/dashboard/profile" }, // Link to profile page
      ],
    },
    {
        title: "Support",
        list: [
          { name: "Support",
            path: "/dashboard/support" }, // Link to support page
        ],
      },
      {
        title: "Settings",
        list: [
          { name: "Preferences",
            path: "/dashboard/settings" }, // Link to settings page
        ],
      },
      {
        title: "Logout",
        list: [
          { name: "Logout", 
            path: "/dashboard/logout" }, // Link to logout page
        ],
      },
      
  ];

  return (
    <div className={styles.container}>
      {menuItems.map((menu, index) => (
        <div key={index} className={styles.menuSection}>
          <h3 className={styles.menuTitle}>{menu.title}</h3>
          <ul className={styles.menuList}>
            {menu.list.map((item, idx) => (
              <li key={idx} className={styles.menuItem}>
                <Link href={item.path}>
                  {item.name}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
