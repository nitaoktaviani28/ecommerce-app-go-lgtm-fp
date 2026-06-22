package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"time"

	"github.com/ecommerce/observability"
)

type OrderItem struct {
	ProductID string  `json:"product_id"`
	Name      string  `json:"name"`
	Price     float64 `json:"price"`
	Quantity  int     `json:"quantity"`
}

type Order struct {
	ID        string      `json:"id"`
	UserID    string      `json:"user_id"`
	Items     []OrderItem `json:"items"`
	Total     float64     `json:"total"`
	Status    string      `json:"status"`
	CreatedAt time.Time   `json:"created_at"`
}

var orders []Order
var orderCounter = 0

func main() {
	mux := http.NewServeMux()

	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprintf(w, `{"status":"healthy","service":"order-service"}`)
	})

	mux.HandleFunc("/orders", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")

		if r.Method == http.MethodPost {
			var order Order
			if err := json.NewDecoder(r.Body).Decode(&order); err != nil {
				log.Printf("[ORDER] Create failed: %v", err)
				w.WriteHeader(http.StatusBadRequest)
				fmt.Fprintf(w, `{"error":"invalid request"}`)
				return
			}
			orderCounter++
			order.ID = fmt.Sprintf("ORD-%05d", orderCounter)
			order.CreatedAt = time.Now()
			order.Status = "pending"

			var total float64
			for _, item := range order.Items {
				total += item.Price * float64(item.Quantity)
			}
			order.Total = total

			orders = append(orders, order)
			log.Printf("[ORDER] Created order=%s user=%s items=%d total=%.2f", order.ID, order.UserID, len(order.Items), order.Total)
			w.WriteHeader(http.StatusCreated)
			json.NewEncoder(w).Encode(order)
			return
		}

		// GET - return orders, optionally filter by user_id
		userID := r.URL.Query().Get("user_id")
		if userID != "" {
			var userOrders []Order
			for _, o := range orders {
				if o.UserID == userID {
					userOrders = append(userOrders, o)
				}
			}
			log.Printf("[ORDER] Listing orders for user=%s count=%d", userID, len(userOrders))
			json.NewEncoder(w).Encode(userOrders)
			return
		}

		log.Printf("[ORDER] Listing all orders count=%d", len(orders))
		json.NewEncoder(w).Encode(orders)
	})

	mux.HandleFunc("/orders/", func(w http.ResponseWriter, r *http.Request) {
		id := r.URL.Path[len("/orders/"):]

		// PATCH to update status
		if r.Method == http.MethodPatch {
			var update struct {
				Status string `json:"status"`
			}
			json.NewDecoder(r.Body).Decode(&update)
			for i, o := range orders {
				if o.ID == id {
					orders[i].Status = update.Status
					log.Printf("[ORDER] Updated order=%s status=%s", id, update.Status)
					w.Header().Set("Content-Type", "application/json")
					json.NewEncoder(w).Encode(orders[i])
					return
				}
			}
		}

		for _, o := range orders {
			if o.ID == id {
				w.Header().Set("Content-Type", "application/json")
				json.NewEncoder(w).Encode(o)
				return
			}
		}
		w.WriteHeader(http.StatusNotFound)
		fmt.Fprintf(w, `{"error":"order not found"}`)
	})

	observability.Run("order-service", mux)
}
