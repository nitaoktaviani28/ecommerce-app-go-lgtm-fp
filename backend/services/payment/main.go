package main

import (
	"encoding/json"
	"fmt"
	"log"
	"math/rand"
	"net/http"
	"time"

	"github.com/ecommerce/observability"
)

type Payment struct {
	ID            string    `json:"id"`
	OrderID       string    `json:"order_id"`
	Amount        float64   `json:"amount"`
	Status        string    `json:"status"`
	Method        string    `json:"method"`
	TransactionID string    `json:"transaction_id"`
	CreatedAt     time.Time `json:"created_at"`
}

type PaymentRequest struct {
	OrderID string  `json:"order_id"`
	Amount  float64 `json:"amount"`
	Method  string  `json:"method"`
}

var payments []Payment
var paymentCounter = 0

func generateTxnID() string {
	chars := "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
	b := make([]byte, 12)
	for i := range b {
		b[i] = chars[rand.Intn(len(chars))]
	}
	return "TXN-" + string(b)
}

func main() {
	mux := http.NewServeMux()

	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprintf(w, `{"status":"healthy","service":"payment-service"}`)
	})

	mux.HandleFunc("/payments", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")

		if r.Method == http.MethodPost {
			var req PaymentRequest
			if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
				log.Printf("[PAYMENT] Invalid request: %v", err)
				w.WriteHeader(http.StatusBadRequest)
				fmt.Fprintf(w, `{"error":"invalid request"}`)
				return
			}

			if req.Method == "" {
				req.Method = "credit_card"
			}

			paymentCounter++
			payment := Payment{
				ID:            fmt.Sprintf("PAY-%05d", paymentCounter),
				OrderID:       req.OrderID,
				Amount:        req.Amount,
				Status:        "completed",
				Method:        req.Method,
				TransactionID: generateTxnID(),
				CreatedAt:     time.Now(),
			}
			payments = append(payments, payment)

			log.Printf("[PAYMENT] Processed payment=%s order=%s amount=%.2f method=%s txn=%s",
				payment.ID, payment.OrderID, payment.Amount, payment.Method, payment.TransactionID)

			w.WriteHeader(http.StatusCreated)
			json.NewEncoder(w).Encode(payment)
			return
		}

		// GET - filter by order_id if provided
		orderID := r.URL.Query().Get("order_id")
		if orderID != "" {
			var orderPayments []Payment
			for _, p := range payments {
				if p.OrderID == orderID {
					orderPayments = append(orderPayments, p)
				}
			}
			log.Printf("[PAYMENT] Listing payments for order=%s count=%d", orderID, len(orderPayments))
			json.NewEncoder(w).Encode(orderPayments)
			return
		}

		log.Printf("[PAYMENT] Listing all payments count=%d", len(payments))
		json.NewEncoder(w).Encode(payments)
	})

	observability.Run("payment-service", mux)
}