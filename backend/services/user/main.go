package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"time"

	"github.com/ecommerce/observability"
)

type User struct {
	ID       int    `json:"id"`
	Name     string `json:"name"`
	Email    string `json:"email"`
	Password string `json:"password,omitempty"`
	Role     string `json:"role"`
}

type AuthRequest struct {
	Email    string `json:"email"`
	Password string `json:"password"`
	Name     string `json:"name,omitempty"`
}

type AuthResponse struct {
	Token string `json:"token"`
	User  User   `json:"user"`
}

var users = []User{
	{ID: 1, Name: "John Doe", Email: "john@example.com", Password: "password123", Role: "customer"},
	{ID: 2, Name: "Jane Smith", Email: "jane@example.com", Password: "password123", Role: "admin"},
	{ID: 3, Name: "Demo User", Email: "demo@shop.com", Password: "demo123", Role: "customer"},
}

func handleLogin(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}

	var req AuthRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		w.WriteHeader(http.StatusBadRequest)
		fmt.Fprintf(w, `{"error":"invalid request"}`)
		return
	}

	for _, u := range users {
		if u.Email == req.Email && u.Password == req.Password {
			log.Printf("[AUTH] Login success user=%s email=%s", u.Name, u.Email)
			resp := AuthResponse{
				Token: fmt.Sprintf("token_%d_%d", u.ID, time.Now().Unix()),
				User:  User{ID: u.ID, Name: u.Name, Email: u.Email, Role: u.Role},
			}
			w.Header().Set("Content-Type", "application/json")
			json.NewEncoder(w).Encode(resp)
			return
		}
	}

	log.Printf("[AUTH] Login failed email=%s", req.Email)
	w.WriteHeader(http.StatusUnauthorized)
	fmt.Fprintf(w, `{"error":"invalid email or password"}`)
}

func handleRegister(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}

	var req AuthRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		w.WriteHeader(http.StatusBadRequest)
		fmt.Fprintf(w, `{"error":"invalid request"}`)
		return
	}

	for _, u := range users {
		if u.Email == req.Email {
			log.Printf("[AUTH] Register failed - email exists: %s", req.Email)
			w.WriteHeader(http.StatusConflict)
			fmt.Fprintf(w, `{"error":"email already registered"}`)
			return
		}
	}

	newUser := User{
		ID:       len(users) + 1,
		Name:     req.Name,
		Email:    req.Email,
		Password: req.Password,
		Role:     "customer",
	}
	users = append(users, newUser)

	log.Printf("[AUTH] Register success user=%s email=%s", newUser.Name, newUser.Email)
	resp := AuthResponse{
		Token: fmt.Sprintf("token_%d_%d", newUser.ID, time.Now().Unix()),
		User:  User{ID: newUser.ID, Name: newUser.Name, Email: newUser.Email, Role: newUser.Role},
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(resp)
}

func getUsers(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	log.Printf("[USER] Listing %d users", len(users))
	safeUsers := make([]User, len(users))
	for i, u := range users {
		safeUsers[i] = User{ID: u.ID, Name: u.Name, Email: u.Email, Role: u.Role}
	}
	json.NewEncoder(w).Encode(safeUsers)
}

func health(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	fmt.Fprintf(w, `{"status":"healthy","service":"user-service"}`)
}

func main() {
	mux := http.NewServeMux()

	mux.HandleFunc("/health", health)
	mux.HandleFunc("/users", getUsers)
	mux.HandleFunc("/auth/login", handleLogin)
	mux.HandleFunc("/auth/register", handleRegister)

	observability.Run("user-service", mux)
}