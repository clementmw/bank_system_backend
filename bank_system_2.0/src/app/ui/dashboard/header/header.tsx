import { MdManageAccounts } from "react-icons/md";
import { CiBellOn, CiSearch } from "react-icons/ci";

export default function Header() {
  return (
    // Header with a search bar, notification, and settings
    <div className="flex gap-4 justify-end p-4 mr-2 text-white">
      
      {/* Search Bar */}
      <div className="flex items-center space-x-2">
        <CiSearch size={20} />
        <input
          type="text"
          name="search"
          placeholder="Search..."
          className="bg-gray-700 text-sm px-2 py-2 rounded-lg outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {/* Notification */}
      <div className="flex items-center space-x-2">
        <button className="text-sm hover:bg-gray-600 focus:ring-2 focus:ring-blue-500">
        <CiBellOn size={20}/>
        </button>
      </div>

      {/* Settings */}
      <div className="flex items-center space-x-2">
        <button className="text-sm  hover:bg-gray-600 focus:ring-2 focus:ring-blue-500">
        <MdManageAccounts size={20}/>
        </button>
      </div>
      
    </div>
  );
}
