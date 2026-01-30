// main.go - Complete Fraud Detection Service
// Run: go run main.go

package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/go-redis/redis/v8"
)
var(
	ctx = context.Background()
	redisclient *redis.Client
)


type TransactionRequest struct {
	Amount             float64 `json:"amount"`
	AccountID          string  `json:"account_id"`
	DestinationAccount string  `json:"destination_account"`
	TransactionType    string  `json:"transaction_type"`
	Timestamp          string  `json:"timestamp"`
}

type FraudResponse struct {
	RiskScore         int               `json:"risk_score"`
	Decision          string            `json:"decision"` // APPROVE, FLAG, BLOCK, CHALLENGE
	Confidence        float64           `json:"confidence"`
	Breakdown         map[string]int    `json:"breakdown"`
	Flags             []string          `json:"flags"`
	Reason            string            `json:"reason"`
	RecommendedAction string            `json:"recommended_action"`
	ProcessingTime    string            `json:"processing_time_ms"`
}

func main() {
	//initialize redis client
	initRedis()

	// Create Gin router (like Django's urlpatterns)
	router := gin.Default()

	// Enable CORS for Django to call this service
	router.Use(corsMiddleware())

	// Define routes (like Django's path())
	router.POST("/api/v1.0/fraud/check", checkFraudHandler)
	router.GET("/health", healthCheckHandler)
	router.GET("/", homeHandler)

	// Start server
	port := ":8080"
	log.Printf("🚀 Fraud Detection Service starting on port %s", port)
	log.Printf("📍 Health check: http://localhost:8080/health")
	log.Printf("📍 API endpoint: http://localhost:8080/api/v1/fraud/check")
	log.Printf("Redis: %s", getRedisUrl())
	
	if err := router.Run(port); err != nil {
		log.Fatal("Failed to start server:", err)
	}
}

// redis initialization
func initRedis(){
	redisURL := getRedisUrl()

	redisclient = redis.NewClient(&redis.Options{
		Addr: redisURL,
		Password: "",
		DB: 0,
		
	})
	// test connection
	_, err := redisclient.Ping(ctx).Result()
	if err != nil{
		log.Printf("Redis connection failed", err)
		redisclient = nil
	}else{
		log.Printf("redis connected successfully")
	}
}
func getRedisUrl() string{
	redisURL := os.Getenv("REDIS_URL")
	if redisURL == ""{
		redisURL  = "localhost:6379"
	}
	return redisURL
}


// Home handler - shows service info
func homeHandler(c *gin.Context) {
	redisStatus := "Connected"
	if redisclient == nil{
		redisStatus = "Not Connected"
	}
	c.JSON(200, gin.H{
		"service":     "Fraud Detection Service",
		"version":     "1.0.0",
		"status":      "running",
		"redis_status": redisStatus,
		"endpoints": map[string]string{
			"health": "/health",
			"check":  "/api/v1/check",
		},
	})
}

// Health check handler
func healthCheckHandler(c *gin.Context) {
	redisHealth := false
	if redisclient != nil{
		_, err := redisclient.Ping(ctx).Result()
		redisHealth = err == nil 

	}
	c.JSON(200, gin.H{
		"status":    "healthy",
		"timestamp": time.Now().Format(time.RFC3339),
		"uptime":    "running",
		"redis": redisHealth,
	})
}

func checkFraudHandler(c *gin.Context) {
	startTime := time.Now()

	var req TransactionRequest

	if err := c.BindJSON(&req); err != nil {
		c.JSON(400, gin.H{
			"error": "Invalid request format",
			"details": err.Error(),
		})
		return
	}

	// Validate request
	if req.Amount <= 0 {
		c.JSON(400, gin.H{
			"error": "Amount must be greater than 0",
		})
		return
	}

	if req.AccountID == "" {
		c.JSON(400, gin.H{
			"error": "Account ID is required",
		})
		return
	}

	// Run fraud detection
	result := detectFraud(req)

	// record the velocity in redis
	if redisclient != nil{
		recordTransaction(req.AccountID, req.Amount)
	}

	// Add processing time
	processingTime := time.Since(startTime).Milliseconds()
	result.ProcessingTime = fmt.Sprintf("%dms", processingTime)

	// Log the check
	log.Printf("🔍 Fraud Check: Amount=%.2f, Decision=%s, Risk=%d, Time=%dms",
		req.Amount, result.Decision, result.RiskScore, processingTime)

	// Return response to Django
	c.JSON(200, result)
}

// ============================================================================
// FRAUD DETECTION LOGIC
// ============================================================================

func detectFraud(txn TransactionRequest) FraudResponse {
	riskScore := 0
	flags := []string{}
	breakdown := make(map[string]int)

	// ========================================
	// RULE 1: Amount-based checks
	// ========================================
	amountRisk := checkAmountRisk(txn.Amount)
	riskScore += amountRisk
	breakdown["amount_risk"] = amountRisk

	if amountRisk > 0 {
		flags = append(flags, "high_amount")
	}

	// ========================================
	// RULE 2: Round amount pattern (suspicious)
	// ========================================
	roundAmountRisk := checkRoundAmount(txn.Amount)
	riskScore += roundAmountRisk
	breakdown["pattern_risk"] = roundAmountRisk

	if roundAmountRisk > 0 {
		flags = append(flags, "round_amount")
	}

	// ========================================
	// RULE 3: Time-based checks
	// ========================================
	timeRisk := checkTimeRisk()
	riskScore += timeRisk
	breakdown["time_risk"] = timeRisk

	if timeRisk > 0 {
		flags = append(flags, "unusual_time")
	}

	// ========================================
	// RULE 4: Transaction type risk
	// ========================================
	typeRisk := checkTransactionTypeRisk(txn.TransactionType)
	riskScore += typeRisk
	breakdown["type_risk"] = typeRisk
	
	// ========================================
	// RULE 5: Velocity checks (unusual patterns)
	// ========================================
	velocityRisk, velocityFlags := checkVelocity(txn.AccountID, txn.Amount) 
	riskScore += velocityRisk
	breakdown["velocity_risk"] = velocityRisk

	if velocityRisk > 0 {
		flags = append(flags, velocityFlags...)
	}

	// ========================================
	// DETERMINE FINAL DECISION
	// ========================================
	decision, reason, recommendedAction := determineDecision(riskScore, flags)

	// Calculate confidence (higher risk = higher confidence in decision)
	confidence := calculateConfidence(riskScore)

	return FraudResponse{
		RiskScore:         riskScore,
		Decision:          decision,
		Confidence:        confidence,
		Breakdown:         breakdown,
		Flags:             flags,
		Reason:            reason,
		RecommendedAction: recommendedAction,
	}
}
// ============================================================================
// VELOCITY CHECK FUNCTIONS

// Check transaction velocity (frequency and amount)
func checkVelocity(accountID string, currentAmount float64) (int, []string) {
	if redisclient == nil {
		return 0, []string{} // Redis not available
	}

	risk := 0
	flags := []string{}

	// Check 1: Transaction count in last 10 minutes
	count10m := getTransactionCount(accountID, "10m")
	if count10m >= 10 {
		risk += 40
		flags = append(flags, "rapid_transactions")
		log.Printf("⚠️  Velocity Alert: %s has %d transactions in 10 minutes", accountID, count10m)
	} else if count10m >= 5 {
		risk += 25
		flags = append(flags, "high_frequency")
	}

	// Check 2: Transaction count in last hour
	count1h := getTransactionCount(accountID, "1h")
	if count1h >= 20 {
		risk += 30
		flags = append(flags, "excessive_hourly_transactions")
		log.Printf("⚠️  Velocity Alert: %s has %d transactions in 1 hour", accountID, count1h)
	}

	// Check 3: Amount accumulation in last hour
	totalAmount1h := getTotalAmount(accountID, "1h")
	if totalAmount1h > 0 {
		// If this transaction + previous hour > 5M, high risk
		if totalAmount1h+currentAmount > 5000000 {
			risk += 35
			flags = append(flags, "large_amount_accumulation")
			log.Printf("⚠️  Velocity Alert: %s total amount in 1h: %.2f", accountID, totalAmount1h)
		} else if totalAmount1h+currentAmount > 2000000 {
			risk += 20
			flags = append(flags, "moderate_amount_accumulation")
		}
	}

	// Check 4: Unique recipients in last hour
	uniqueRecipients := getUniqueRecipients(accountID, "1h")
	if uniqueRecipients >= 10 {
		risk += 25
		flags = append(flags, "multiple_recipients")
		log.Printf("⚠️  Velocity Alert: %s sent to %d recipients in 1h", accountID, uniqueRecipients)
	}

	return risk, flags
}

// Record a transaction for velocity tracking
func recordTransaction(accountID string, amount float64) {
	if redisclient == nil {
		return
	}

	now := time.Now().Unix()

	// Record count (increment with expiry)
	countKey10m := fmt.Sprintf("fraud:velocity:count:10m:%s", accountID)
	countKey1h := fmt.Sprintf("fraud:velocity:count:1h:%s", accountID)

	redisclient.Incr(ctx, countKey10m)
	redisclient.Expire(ctx, countKey10m, 10*time.Minute)

	redisclient.Incr(ctx, countKey1h)
	redisclient.Expire(ctx, countKey1h, 1*time.Hour)

	// Record amount (add to sorted set with timestamp as score)
	amountKey1h := fmt.Sprintf("fraud:velocity:amount:1h:%s", accountID)
	redisclient.ZAdd(ctx, amountKey1h, &redis.Z{
		Score:  float64(now),
		Member: fmt.Sprintf("%.2f", amount),
	})
	redisclient.Expire(ctx, amountKey1h, 1*time.Hour)

}

// Get transaction count for time period
func getTransactionCount(accountID string, period string) int {
	if redisclient == nil {
		return 0
	}

	key := fmt.Sprintf("fraud:velocity:count:%s:%s", period, accountID)
	count, err := redisclient.Get(ctx, key).Int()
	if err != nil {
		return 0
	}
	return count
}

// Get total amount transacted in time period
func getTotalAmount(accountID string, period string) float64 {
	if redisclient == nil {
		return 0
	}

	key := fmt.Sprintf("fraud:velocity:amount:%s:%s", period, accountID)

	// Get all amounts in the time window
	now := time.Now().Unix()
	var cutoff int64

	switch period {
	case "10m":
		cutoff = now - 600
	case "1h":
		cutoff = now - 3600
	case "24h":
		cutoff = now - 86400
	default:
		cutoff = now - 3600
	}

	// Get amounts with score >= cutoff
	amounts, err := redisclient.ZRangeByScore(ctx, key, &redis.ZRangeBy{
		Min: fmt.Sprintf("%d", cutoff),
		Max: "+inf",
	}).Result()

	if err != nil {
		return 0
	}

	// Sum up amounts
	total := 0.0
	for _, amountStr := range amounts {
		amount, _ := strconv.ParseFloat(amountStr, 64)
		total += amount
	}

	return total
}

// Get unique recipient count
func getUniqueRecipients(accountID string, period string) int {
	if redisclient == nil {
		return 0
	}

	key := fmt.Sprintf("fraud:velocity:recipients:%s:%s", period, accountID)
	count, err := redisclient.SCard(ctx, key).Result()
	if err != nil {
		return 0
	}
	return int(count)
}

// ============================================================================
// FRAUD CHECK FUNCTIONS

// Check amount-based risk
func checkAmountRisk(amount float64) int {
	risk := 0

	if amount > 1000000 { // Over 1M
		risk = 50
	} else if amount > 500000 { // Over 500K
		risk = 40
	} else if amount > 200000 { // Over 200K
		risk = 25
	} else if amount > 100000 { // Over 100K
		risk = 15
	}

	return risk
}

// Check for round amount patterns (fraudsters use round numbers)
func checkRoundAmount(amount float64) int {
	intAmount := int(amount)

	// Exactly divisible by 100,000
	if intAmount%100000 == 0 && intAmount >= 100000 {
		return 20
	}

	// Exactly divisible by 50,000
	if intAmount%50000 == 0 && intAmount >= 50000 {
		return 15
	}

	// Exactly divisible by 10,000
	if intAmount%10000 == 0 && intAmount >= 10000 {
		return 10
	}

	return 0
}

// Check time-based risk (unusual hours)
func checkTimeRisk() int {
	hour := time.Now().Hour()

	// Very late night / early morning (2 AM - 6 AM)
	if hour >= 2 && hour <= 6 {
		return 30
	}

	// Late night (11 PM - 2 AM)
	if hour >= 23 || hour <= 2 {
		return 20
	}

	// Very early morning (6 AM - 7 AM)
	if hour >= 6 && hour <= 7 {
		return 10
	}

	return 0
}

// Check transaction type risk
func checkTransactionTypeRisk(txnType string) int {
	switch txnType {
	case "WITHDRAWAL":
		return 10 // Withdrawals slightly riskier
	case "MPESA_WITHDRAWAL":
		return 15 // External withdrawals more risk
	case "INTERNAL_TRANSFER":
		return 5 // Internal transfers lower risk
	default:
		return 0
	}
}

// Determine final decision based on risk score
func determineDecision(riskScore int, flags []string) (string, string, string) {
	decision := "APPROVE"
	reason := "Transaction appears normal"
	recommendedAction := "PROCEED"

	if riskScore >= 80 {
		decision = "BLOCK"
		reason = fmt.Sprintf("Critical fraud risk detected (score: %d). Multiple suspicious patterns identified.", riskScore)
		recommendedAction = "REJECT_TRANSACTION"
	} else if riskScore >= 50 {
		decision = "FLAG"
		reason = fmt.Sprintf("High fraud risk detected (score: %d). Transaction flagged for manual review.", riskScore)
		recommendedAction = "MANUAL_REVIEW"
	} else if riskScore >= 40 {
		decision = "CHALLENGE"
		reason = fmt.Sprintf("Moderate risk detected (score: %d). Additional verification recommended.", riskScore)
		recommendedAction = "REQUIRE_2FA"
	} else if riskScore > 0 {
		decision = "APPROVE"
		reason = fmt.Sprintf("Low risk detected (score: %d). Transaction approved with monitoring.", riskScore)
		recommendedAction = "PROCEED_WITH_LOGGING"
	}

	return decision, reason, recommendedAction
}

// Calculate confidence in decision
func calculateConfidence(riskScore int) float64 {
	if riskScore >= 80 {
		return 0.95 // Very confident in block decision
	} else if riskScore >= 60 {
		return 0.85 // Confident in flag decision
	} else if riskScore >= 40 {
		return 0.75 // Moderately confident
	} else if riskScore > 0 {
		return 0.60 // Some confidence
	}
	return 0.90 // Confident in approval
}

// ============================================================================
// MIDDLEWARE
// ============================================================================

// CORS middleware to allow Django to call this service
func corsMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		c.Writer.Header().Set("Access-Control-Allow-Origin", "*")
		c.Writer.Header().Set("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
		c.Writer.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")

		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(204)
			return
		}

		c.Next()
	}
}
