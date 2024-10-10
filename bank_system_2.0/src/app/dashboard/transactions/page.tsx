"use client"
import React,{useState,useEffect} from "react"
import axios from "axios"

export default function Transactions(){
    const [displayedTransaction, setTransaction] = useState([])
    const [itemsPerPage] = useState(15)
    const [currentPage, setCurrentPage] = useState(1)

    useEffect(()=>{
      const fetchTransaction = async ()=>{
          try{
          const response = await axios.get("http://127.0.0.1:5555/v1.0/transactionshistory")
          setTransaction(response.data)
          console.log("layout console",response.data)
          }
          catch (error){
            console.error("Error fetching transactions:", error);
          }
      }
      
      fetchTransaction()
  
  },[])
//   have pagination for the pages 
 const totalpages = Math.ceil(displayedTransaction.length / itemsPerPage)
 const paginatedTransactions = displayedTransaction.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );
//   handle previous and next 
const goTopage = (pageNumber) => setCurrentPage(pageNumber);
const prevPage = () => setCurrentPage((prev) => Math.max(prev - 1, 1));


    return (
    <div>
        <div className="overflow-x-auto">
        <table className="table table-zebra">
            {/* head */}
            <thead>
            <tr>
                <td></td>
                <th>First Name</th>
                <th>Amount</th>
                <th>Account Number</th>
                <th>Purpose</th>
                <th>Date</th>
                <th>Transaction Type</th>
                <th>Receiver</th>
            </tr>
            </thead>
            <tbody>
                        {/* Check if recentTransaction is an array before mapping */}
                        {paginatedTransactions && paginatedTransactions.length > 0 ? (
                            paginatedTransactions.map((transaction) => (
                                <tr key={transaction.id}>
                                    <td>{transaction.id}</td>
                                    <td>{transaction.user.firstName}</td>
                                    <td>{transaction.amount}</td>
                                    <td>{transaction.account.account_number}</td>
                                    <td>{transaction.description}</td>
                                    <td>{new Date(transaction.created_at).toLocaleDateString()}</td>
                                    <td>{transaction.transaction_type}</td>
                                    <td>{transaction.receiver || 'N/A'}</td>
                                </tr>
                            ))
                        ) : (
                            <tr>
                                <td colSpan="7">No transactions available</td>
                            </tr>
                        )}
                    </tbody>
        </table>
        <div className="join grid grid-cols-2">
            <button
            onClick={()=> prevPage(currentPage -1 )}
            disabled = {currentPage === 1}
            
            className="join-item btn btn-outline">Previous page</button>
            
            <button
                onClick={()=> goTopage(currentPage +1)}
                disabled = {currentPage === totalpages}    
            className="join-item btn btn-outline">Next</button>
        </div>
        </div>

        
    </div>
    );
}