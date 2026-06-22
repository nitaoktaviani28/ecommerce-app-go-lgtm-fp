package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"

	"github.com/ecommerce/observability"
)

type Product struct {
	ID       string  `json:"id"`
	Name     string  `json:"name"`
	Price    float64 `json:"price"`
	Stock    int     `json:"stock"`
	Category string  `json:"category"`
	Image    string  `json:"image"`
}

var products = []Product{
	{ID: "1", Name: "MacBook Pro 14\" M3", Price: 1999.99, Stock: 15, Category: "Laptop", Image: "https://store.storeimages.cdn-apple.com/4982/as-images.apple.com/is/mbp14-spacegray-select-202310"},
	{ID: "2", Name: "iPhone 15 Pro Max", Price: 1199.99, Stock: 30, Category: "Smartphone", Image: "https://store.storeimages.cdn-apple.com/4982/as-images.apple.com/is/iphone-15-pro-max-blue-titanium"},
	{ID: "3", Name: "Samsung Galaxy S24 Ultra", Price: 1099.99, Stock: 25, Category: "Smartphone", Image: "https://images.samsung.com/is/image/samsung/p6pim/id/galaxy-s24-ultra"},
	{ID: "4", Name: "Sony WH-1000XM5", Price: 349.99, Stock: 40, Category: "Audio", Image: "https://m.media-amazon.com/images/I/51aXvjzcukL._AC_SL1500_.jpg"},
	{ID: "5", Name: "iPad Air M2", Price: 799.99, Stock: 20, Category: "Tablet", Image: "https://store.storeimages.cdn-apple.com/4982/as-images.apple.com/is/ipad-air-select-wifi-blue"},
	{ID: "6", Name: "Logitech MX Master 3S", Price: 99.99, Stock: 60, Category: "Accessories", Image: "https://m.media-amazon.com/images/I/61ni3t1ryQL._AC_SL1500_.jpg"},
	{ID: "7", Name: "Samsung 4K Smart TV 55\"", Price: 699.99, Stock: 10, Category: "Electronics", Image: "https://images.samsung.com/is/image/samsung/p6pim/id/ua55cu8000kxxd"},
	{ID: "8", Name: "Nike Air Max 270", Price: 149.99, Stock: 45, Category: "Fashion", Image: "https://static.nike.com/a/images/t_PDP_1280_v1/f_auto,q_auto:eco/air-max-270"},
	{ID: "9", Name: "Mechanical Keyboard RGB", Price: 129.99, Stock: 35, Category: "Accessories", Image: "https://m.media-amazon.com/images/I/71Xq0JoMFrL._AC_SL1500_.jpg"},
	{ID: "10", Name: "GoPro Hero 12", Price: 399.99, Stock: 18, Category: "Electronics", Image: "https://m.media-amazon.com/images/I/61p2fYPGMEL._AC_SL1500_.jpg"},
	{ID: "11", Name: "Adidas Ultraboost 23", Price: 189.99, Stock: 50, Category: "Fashion", Image: "https://assets.adidas.com/images/h_840,f_auto,q_auto,fl_lossy,c_fill/ultraboost"},
	{ID: "12", Name: "Nintendo Switch OLED", Price: 349.99, Stock: 22, Category: "Gaming", Image: "https://assets.nintendo.com/image/upload/ncom/en_US/switch/oled-model"},
}

func main() {
	mux := http.NewServeMux()

	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		fmt.Fprintf(w, `{"status":"healthy","service":"product-service"}`)
	})

	mux.HandleFunc("/products", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		log.Printf("[PRODUCT] Returning %d products", len(products))
		json.NewEncoder(w).Encode(products)
	})

	mux.HandleFunc("/products/", func(w http.ResponseWriter, r *http.Request) {
		id := r.URL.Path[len("/products/"):]
		for _, p := range products {
			if p.ID == id {
				w.Header().Set("Content-Type", "application/json")
				log.Printf("[PRODUCT] Found product id=%s name=%s", p.ID, p.Name)
				json.NewEncoder(w).Encode(p)
				return
			}
		}
		log.Printf("[PRODUCT] Product not found id=%s", id)
		w.WriteHeader(http.StatusNotFound)
		fmt.Fprintf(w, `{"error":"product not found"}`)
	})

	observability.Run("product-service", mux)
}
