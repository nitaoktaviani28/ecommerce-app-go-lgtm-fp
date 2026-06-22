package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"time"
)

type Payment struct {
	ID            int       `json:"id"`
	OrderID       int       `json:"order_id"`
	Amount        float64   `json:"amount"`
	Status        string    `json:"status"`
	Method        string    `json:"method"`
	TransactionID string    `json:"transaction_id,omitempty"`
	CreatedAt     time.Time `json:"created_at"`
}

var payments = []Payment{
	{ID: 1, OrderID: 1, Amount: 999.99, Status: "completed", Method: "credit_card", TransactionID: "txn_001", CreatedAt: time.Now()},
	{ID: 2, OrderID: 2, Amount: 59.98, Status: "pending", Method: "bank_transfer", TransactionID: "txn_002", CreatedAt: time.Now()},
}

func getPayments(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(payments)
}

func getPaymentByID(w http.ResponseWriter, r *http.Request) {
	id := r.URL.Query().Get("id")
	if id == "" {
		w.WriteHeader(http.StatusBadRequest)
		fmt.Fprintf(w, `{"error":"id required"}`)
		return
	}

	for _, p := range payments {
		if fmt.Sprintf("%d", p.ID) == id {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusOK)
			json.NewEncoder(w).Encode(p)
			return
		}
	}

	w.WriteHeader(http.StatusNotFound)
	fmt.Fprintf(w, `{"error":"payment not found"}`)
}

func processPayment(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}

	var payment Payment
	if err := json.NewDecoder(r.Body).Decode(&payment); err != nil {
		w.WriteHeader(http.StatusBadRequest)
		fmt.Fprintf(w, `{"error":"invalid request"}`)
		return
	}

	payment.ID = len(payments) + 1
	payment.CreatedAt = time.Now()
	payment.Status = "completed"
	payment.TransactionID = fmt.Sprintf("txn_%03d", payment.ID)
	payments = append(payments, payment)

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(payment)
}

func health(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	fmt.Fprintf(w, `{"status":"healthy","service":"payment-service"}`)
}

func main() {
	mux := http.NewServeMux()

	mux.HandleFunc("/health", health)
	mux.HandleFunc("/payments", getPayments)
	mux.HandleFunc("/payments/get", getPaymentByID)
	mux.HandleFunc("/payments/process", processPayment)

	log.Println("Payment Service running on :8080")
	log.Fatal(http.ListenAndServe(":8080", mux))
}