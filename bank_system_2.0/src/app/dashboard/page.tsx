"use client"
import Chart from "../ui/dashboard/chats/chart";
import Rightbar from "../ui/dashboard/rightbar/rightbar";
import Recenttra from "../ui/dashboard/transaction/recenttra";
import Card from "../ui/dashboard/card/card";
import { useEffect, useState } from "react";  
import axios from "axios";
import {Api_Url} from "@/app/dashboard/utility";

const Page = () => {
  const [transaction, setTransaction] = useState([])
  const [errorMsg, setErrorMsg] = useState("")
  const APIURL = Api_Url

  useEffect(()=>{
    const fetchTransaction = async ()=>{
        try{
        const response = await axios.get("http://127.0.0.1:5555/v1.0/transactionshistory")
        const sortedTransactions = response.data.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        setTransaction(sortedTransactions);
        console.log(response.data)
        }
        catch (error){
          console.error("Error fetching transactions:", error);
        }
    }
    
    fetchTransaction()

},[])

const recentTransactions = transaction.slice(0, 10);



  return (
    <div className="flex relative h-screen overflow-hidden">      
      {/* Main Content Area */}
      <div className="flex-1">
        
        {/* Greeting Section */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-800">Hello, User!</h1> {/* Replace "User" with the user's name from session */}
        </div>
        
        {/* Cards Section */}
        <div className="">
          {/* <Card /> */}
        </div>
        
        {/* Recent Transactions Section */}
        <div className="mb-8">
          <h2 className="text-xl font-semibold text-gray-700 mb-4">Recent Transactions</h2>
          <Recenttra  displayedTransaction={recentTransactions} />
        </div>
        
        {/* Chart Section */}
        <div className="mb-8">
          <h2 className="text-xl font-semibold text-gray-700 mb-4">Financial Overview</h2>
          <Chart />
        </div>
      </div>
      
      {/* Right Sidebar */} 
      <div className="w-full lg:w-1/4 bg-gray-300">
        <Rightbar />
       </div>
    </div>
  );
};

export default Page;
