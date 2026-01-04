# Toast POS API Integration Research Summary

_Generated: 2026-01-03 | Sources: 15+ | Confidence: High_

## Executive Summary

<key-findings>

- **Primary Recommendation**: Toast POS API is well-suited for voice AI order placement with full support for takeout, delivery, and dine-in orders through the Orders API
- **Critical Requirement**: Must become a Toast Integration Partner (multi-stage approval process) to get API credentials
- **Payment Flexibility**: Orders can be created WITHOUT payment (pay-at-pickup) or WITH payment (credit card via separate Credit Cards API)
- **Real-time Updates**: Webhooks available for order status notifications, enabling confirmation callbacks to voice agents
- **Key Limitation**: No cash orders or Toast gift cards via API; requires 2-step price calculation before order submission

</key-findings>

---

## 1. API Overview & Architecture

<overview>

### Base URLs
| Environment | Hostname |
|-------------|----------|
| Production | `https://[toast-api-hostname]` (provided by Toast) |
| Sandbox | `https://[sandbox-hostname]` (provided during development) |

### Core APIs for Voice Integration
| API | Purpose | Key Endpoints |
|-----|---------|---------------|
| **Authentication API** | OAuth 2.0 token management | `/authentication/v1/authentication/login` |
| **Orders API** | Create, update, retrieve orders | `/orders/v2/orders`, `/orders/v2/prices` |
| **Menus API** | Retrieve menu items, modifiers | `/menus/v2/menus` |
| **Configuration API** | Get dining options, tables, etc. | `/config/v2/diningOptions`, `/config/v2/menuItems` |
| **Credit Cards API** | Authorize card payments | `/creditcards/v1/authorization` |
| **Webhooks** | Real-time order updates | `order_updated` event |

### API Capabilities
- **Read Operations**: GET requests for menus, orders, configuration
- **Write Operations**: POST, PUT, PATCH, DELETE for orders, payments
- **Outbound APIs**: Webhooks sending data from Toast to your integration

</overview>

---

## 2. Authentication

<authentication>

### OAuth 2.0 Client Credentials Flow

Toast uses the **OAuth 2.0 client-credentials grant type**. No user interaction required - ideal for server-to-server voice agent integrations.

### Getting an Authentication Token

**Endpoint:**
```
POST https://[toast-api-hostname]/authentication/v1/authentication/login
```

**Request Body:**
```json
{
  "clientId": "your-client-id",
  "clientSecret": "your-client-secret",
  "userAccessType": "TOAST_MACHINE_CLIENT"
}
```

**cURL Example:**
```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "clientId": "your-client-id",
    "clientSecret": "your-client-secret",
    "userAccessType": "TOAST_MACHINE_CLIENT"
  }' \
  https://[toast-api-hostname]/authentication/v1/authentication/login
```

**Response:**
```json
{
  "token": {
    "tokenType": "Bearer",
    "expiresIn": 19168,
    "accessToken": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
  },
  "status": "SUCCESS"
}
```

### Token Expiration
- `expiresIn`: Seconds until expiration (typically ~5-6 hours)
- Must refresh token before expiration
- Store tokens securely; never commit to repositories

### Required Headers for All API Calls
```http
Authorization: Bearer {access-token}
Toast-Restaurant-External-ID: {restaurant-guid}
Content-Type: application/json
```

### Credential Types
| Integration Type | How to Get Credentials |
|------------------|------------------------|
| Partner Integration | Toast team creates after approval |
| Custom Integration | Toast team creates after approval |
| Standard/Analytics | Self-service via Toast Web |

</authentication>

---

## 3. Order Creation API

<order-creation>

### Order Creation Flow (2-Step Process)

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Build Order    │────▶│  Get Prices     │────▶│  POST Order     │
│  JSON Object    │     │  /prices        │     │  /orders        │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

**Critical**: You MUST call `/prices` before `/orders` - it's the only supported way to calculate totals.

### Step 1: Build Order Object

**Minimum Required Fields:**
```json
{
  "entityType": "Order",
  "diningOption": {
    "guid": "{dining-option-guid}",
    "entityType": "DiningOption"
  },
  "checks": [{
    "entityType": "Check",
    "selections": [{
      "entityType": "MenuItemSelection",
      "itemGroup": {
        "guid": "{menu-group-guid}"
      },
      "item": {
        "guid": "{menu-item-guid}"
      },
      "quantity": 1,
      "modifiers": []
    }],
    "customer": {
      "entityType": "Customer",
      "firstName": "John",
      "lastName": "Doe",
      "phone": "5551234567",
      "email": "john.doe@example.com"
    }
  }]
}
```

### Step 2: Get Prices

**Endpoint:**
```
POST https://[toast-api-hostname]/orders/v2/prices
```

**Request:** Send your Order object

**Response:** Returns Order object with calculated prices:
```json
{
  "checks": [{
    "amount": 15.99,
    "taxAmount": 1.28,
    "totalAmount": 17.27
  }]
}
```

### Step 3: Submit Order

**Endpoint:**
```
POST https://[toast-api-hostname]/orders/v2/orders
```

**Request:** Send Order object (optionally with payment info)

**Response:** Complete Order object with generated GUIDs:
```json
{
  "guid": "017fdd94-4a30-4657-9475-b1a684758531",
  "displayNumber": "42",
  "checks": [{
    "guid": "c1784eaf-7ca8-461a-ba38-795ec51cf84a",
    "displayNumber": "1"
  }],
  "approvalStatus": "APPROVED"
}
```

### Confirmation Number / Display Number

The `displayNumber` field serves as the order confirmation number:
- Generally starts at 1 each day and counts up
- **Not guaranteed unique** across days
- Can be empty if unset
- Recommendation: Use `tabName` for custom order numbers: "YourCompany - 12345"

For reliable tracking, use the returned `guid` (GUID) which is guaranteed unique.

</order-creation>

---

## 4. Order Types by Dining Option

<dining-options>

### Dining Option Types
| Behavior | Description | Required Fields |
|----------|-------------|-----------------|
| `DINE_IN` | Guest eats at restaurant | `diningOption`, `checks` |
| `TAKE_OUT` | Guest picks up | `diningOption`, `checks`, `customer` |
| `DELIVERY` | Delivered to guest | `diningOption`, `checks`, `customer`, `deliveryInfo` |
| Curbside | Staff brings to vehicle | `diningOption`, `checks`, `customer`, `curbsidePickupInfo` |

### Takeout Order Example (Voice Agent Use Case)
```json
{
  "entityType": "Order",
  "diningOption": {
    "guid": "d527b5cf-96d2-41dc-92e6-8e9ca1ed36bd",
    "entityType": "DiningOption"
  },
  "promisedDate": "2026-01-03T18:30:00.000+0000",
  "checks": [{
    "entityType": "Check",
    "selections": [{
      "entityType": "MenuItemSelection",
      "itemGroup": {"guid": "205c4612-d04d-43ec-86fd-7d0827a2eeed"},
      "item": {"guid": "c58b958e-85a0-485a-bb5c-3b588e056aff"},
      "quantity": 2,
      "modifiers": [{
        "entityType": "MenuItemSelection",
        "optionGroup": {"guid": "mod-group-guid"},
        "item": {"guid": "modifier-item-guid"},
        "quantity": 1
      }]
    }],
    "customer": {
      "entityType": "Customer",
      "firstName": "John",
      "lastName": "Doe",
      "phone": "5551234567",
      "email": "john.doe@example.com"
    }
  }]
}
```

### Delivery Order Example
```json
{
  "entityType": "Order",
  "diningOption": {
    "guid": "delivery-dining-option-guid",
    "entityType": "DiningOption"
  },
  "deliveryInfo": {
    "address1": "123 Main Street",
    "address2": "Apt 4B",
    "city": "Boston",
    "state": "MA",
    "zipCode": "02101",
    "notes": "Ring doorbell twice"
  },
  "checks": [{
    "entityType": "Check",
    "selections": [...],
    "customer": {
      "entityType": "Customer",
      "firstName": "Jane",
      "lastName": "Smith",
      "phone": "5559876543",
      "email": "jane.smith@example.com"
    }
  }]
}
```

### Curbside Pickup Example
```json
{
  "entityType": "Order",
  "diningOption": {
    "guid": "curbside-dining-option-guid",
    "entityType": "DiningOption"
  },
  "curbsidePickupInfo": {
    "transportDescription": "Red Honda Civic",
    "transportColor": "Red",
    "notes": "Parking spot 5"
  },
  "checks": [{...}]
}
```

### Getting Available Dining Options
```
GET https://[toast-api-hostname]/config/v2/diningOptions
Headers:
  Authorization: Bearer {token}
  Toast-Restaurant-External-ID: {restaurant-guid}
```

</dining-options>

---

## 5. Payment Options

<payments>

### Option A: No Payment (Pay-at-Pickup / Pay-in-Store)

**Perfect for voice agents** - simply omit the `payments` array from the Check object:

```json
{
  "checks": [{
    "entityType": "Check",
    "selections": [...],
    "customer": {...}
    // No "payments" field = pay when customer arrives
  }]
}
```

The order is created and sent to the kitchen. Customer pays at the register when picking up.

### Option B: Alternative Payment Type (Pre-paid via External System)

For orders paid through your own payment system:

```json
{
  "checks": [{
    "entityType": "Check",
    "selections": [...],
    "customer": {...},
    "payments": [{
      "type": "OTHER",
      "amount": 17.27,
      "tipAmount": 3.00,
      "amountTendered": 17.27,
      "paidDate": "2026-01-03T16:24:09.000+0000",
      "otherPayment": {
        "guid": "0dc19214-d29e-4ab9-a773-27e5812999c7"
      }
    }]
  }]
}
```

**Get Alternative Payment Types:**
```
GET https://[toast-api-hostname]/config/v2/alternativePaymentTypes
```

### Option C: Credit Card Payment (via Credit Cards API)

**3-Step Process:**

1. **Get encryption key** from Toast integrations team
2. **Authorize the card:**
```
PUT https://[toast-api-hostname]/creditcards/v1/merchants/{merchantGuid}/payments/{paymentGuid}
```

**Authorization Request Body:**
```json
{
  "paymentType": "CARD_PRESENT",
  "orderGuid": "order-guid",
  "checkGuid": "check-guid",
  "amount": 17.27,
  "tipAmount": 3.00,
  "keyId": "RSA-OAEP-SHA256::key-id",
  "encryptedCardData": "{encrypted-card-data}",
  "cardNumberOrigin": "CUSTOMER_DIRECT",
  "guestIdentifier": "guest-12345"
}
```

3. **Apply payment to check** (within 5 minutes of authorization):
```
POST https://[toast-api-hostname]/orders/v2/orders/{orderGuid}/checks/{checkGuid}/payments
```

**Important Timing:**
- Apply payment within **5 minutes** of authorization
- Capture payment within **7 days**
- Otherwise, payment is automatically voided

### Payment Limitations
- No cash orders via API
- No Toast gift cards via API
- No third-party gift cards via API
- No Toast loyalty functionality via API

</payments>

---

## 6. Menu Synchronization

<menus>

### Menus API (Recommended for Ordering Integrations)

**Get Full Menu:**
```
GET https://[toast-api-hostname]/menus/v2/menus
Headers:
  Authorization: Bearer {token}
  Toast-Restaurant-External-ID: {restaurant-guid}
```

**Check for Updates (before full fetch):**
```
GET https://[toast-api-hostname]/menus/v2/metadata
```

### Menu Structure
```
Restaurant
├── Menu (Breakfast, Lunch, Dinner)
│   ├── MenuGroup (Appetizers, Entrees, Desserts)
│   │   ├── MenuItem (Burger, Salad, Steak)
│   │   │   ├── MenuOptionGroup (Toppings, Sides)
│   │   │   │   └── MenuItem (Modifier options)
```

### Configuration API (Alternative)

For individual entity lookups:
```
GET /config/v2/menuItems?lastModified={timestamp}
GET /config/v2/menuGroups?lastModified={timestamp}
GET /config/v2/menus?lastModified={timestamp}
```

### API Versions
- **Menus API V3**: Use for ordering integrations
- **Menus API V2**: Use for other integration types

</menus>

---

## 7. Webhooks & Real-Time Updates

<webhooks>

### Orders Webhook

Receive real-time notifications when orders are created or updated.

**Event Types:**
| Event | Description |
|-------|-------------|
| `order_updated` | Standard order create/update |
| `channel_order_updated` | Channel-specific order updates |

**Webhook Payload Structure:**
```json
{
  "timestamp": "2026-01-03T16:24:09.000+0000",
  "eventCategory": "order_updated",
  "eventType": "order_updated",
  "guid": "webhook-event-guid",
  "details": {
    "restaurantGuid": "restaurant-guid",
    "order": {
      // Full Order object (same as GET /orders/{guid} response)
    },
    "appliedPackagingInfo": {...}
  }
}
```

**Important Notes:**
- Payload sizes can reach **600KB+** - ensure your servers can handle this
- PII is **omitted** from webhook payloads (firstName, lastName, phone, address)
- Use separate GET request to `/orders/{guid}` for full customer details
- Implement idempotency using `guid` to prevent duplicate processing

### Guest Order Fulfillment Status Webhook

Track order preparation stages:

**Fulfillment Statuses:**
| Status | Description |
|--------|-------------|
| `RECEIVED` | Initial state (all orders) |
| `IN_PREPARATION` | Order being prepared |
| `READY` | Ready for pickup/delivery |
| `FULFILLED` | Order completed |

### Restaurant Availability Webhook

Monitor if restaurant can accept online orders:
- Triggered when Autofire device stops approving orders
- Use for pausing voice agent order acceptance

### Webhook Best Practices
1. **Return 2xx immediately** - process events asynchronously
2. **Implement fallback polling** - periodically query orders API
3. **Use event GUID for idempotency** - prevent duplicate processing
4. **Handle large payloads** - configure CDN/servers for 600KB+

### Adding Webhook Subscription
Configure through Toast Developer Portal or contact Toast integrations team.

</webhooks>

---

## 8. Rate Limits

<rate-limits>

### Global Rate Limits
| Limit Type | Threshold |
|------------|-----------|
| Per second | 20 requests |
| Per 15 minutes | 10,000 requests |

### Endpoint-Specific Limits
| Endpoint | Limit |
|----------|-------|
| `GET /menus` | 1 request/second/location |
| `GET /ordersBulk` | 5 requests/second/location |
| `/ordersBulk` historical | Max 1 month intervals, 5-10 second spacing |

### Rate Limit Behavior
- **HTTP 429** returned when limit exceeded
- Limits applied **per restaurant location** when `Toast-Restaurant-External-ID` header present
- Limits applied **per IP address** when header absent

### Best Practices
- Cache menu data; use `/menus/v2/metadata` to check for changes
- Implement exponential backoff for 429 responses
- Batch order queries where possible

</rate-limits>

---

## 9. Developer Requirements

<developer-requirements>

### Integration Partnership Process

```
Application → Discovery → Agreement → Development → Certification → Alpha → Beta → GA
```

**Stage Details:**

| Stage | Duration | Requirements |
|-------|----------|--------------|
| **Application** | Varies | Submit application (high volume, not all approved) |
| **Discovery** | Weeks | Business assessment, technical readiness review |
| **Partner Agreement** | Days | Legal, compliance, privacy, security approval |
| **Development** | 4-8 weeks | Receive sandbox credentials, build integration |
| **Certification** | 1 hour | Live demo of integration workflows |
| **Alpha** | ~1 week | Single restaurant production test |
| **Beta** | Several weeks | 3-5 restaurants, co-marketing development |
| **General Availability** | - | Listed on Toast integrations site |

### Sandbox Environment

**Features:**
- Fully functional APIs (versioned like production)
- Simulated payment processing
- Downloadable Toast POS Android APK for testing
- Separate credentials from production

**Getting Sandbox Access:**
1. Submit application via Toast Developer Portal
2. Get approved for partnership
3. Receive sandbox credentials from Toast integrations team

### Developer Portal

**URL:** https://dev.toasttab.com/

**Features:**
- View/manage API credentials
- View connected restaurants
- Manage API scopes
- Switch between sandbox/production environments
- Access technical documentation

### Required Scopes (Varies by Integration)

For ordering integration, typically need:
- `orders:read`
- `orders:write`
- `menus:read`
- `config:read`
- (Additional scopes for payments, webhooks)

### Documentation Resources

| Resource | URL |
|----------|-----|
| Developer Portal | https://dev.toasttab.com/ |
| Developer Guide | https://doc.toasttab.com/doc/devguide/index.html |
| API Reference | https://toastintegrations.redoc.ly/openapi/ |
| Orders API Docs | https://doc.toasttab.com/doc/devguide/portalOrdersApiOverview.html |

</developer-requirements>

---

## 10. Voice AI Integration Patterns

<voice-integration>

### Recommended Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Voice Agent    │────▶│  Voice Backend  │────▶│  Toast API      │
│  (Phone/Web)    │     │  (Your Server)  │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌─────────────────┐
                        │  Menu Cache     │
                        │  (Redis/DB)     │
                        └─────────────────┘
```

### Voice Agent Tool Functions

**1. Get Menu Items:**
```python
async def get_menu_items(restaurant_guid: str) -> dict:
    """Retrieve available menu items for voice agent to read."""
    # Check cache first
    cached = await redis.get(f"menu:{restaurant_guid}")
    if cached:
        return json.loads(cached)

    # Fetch from Toast API
    menu = await toast_client.get_menus(restaurant_guid)
    await redis.set(f"menu:{restaurant_guid}", json.dumps(menu), ex=3600)
    return menu
```

**2. Create Order:**
```python
async def create_order(
    restaurant_guid: str,
    items: list[dict],
    customer_name: str,
    customer_phone: str,
    customer_email: str,
    dining_option: str = "TAKE_OUT",
    promised_time: str = None
) -> dict:
    """Create order from voice agent selections."""

    # Build order object
    order = {
        "entityType": "Order",
        "diningOption": {"guid": dining_option_guid},
        "promisedDate": promised_time,
        "checks": [{
            "entityType": "Check",
            "selections": items,
            "customer": {
                "firstName": customer_name.split()[0],
                "lastName": customer_name.split()[-1],
                "phone": customer_phone.replace("-", ""),
                "email": customer_email
            }
        }]
    }

    # Get prices
    priced_order = await toast_client.get_prices(restaurant_guid, order)

    # Submit order
    result = await toast_client.create_order(restaurant_guid, priced_order)

    return {
        "confirmation_number": result["guid"],  # Use GUID for reliability
        "display_number": result.get("displayNumber"),
        "total": result["checks"][0]["totalAmount"],
        "estimated_time": result.get("estimatedFulfillmentDate")
    }
```

**3. Check Order Status:**
```python
async def get_order_status(restaurant_guid: str, order_guid: str) -> dict:
    """Get current order status for customer inquiry."""
    order = await toast_client.get_order(restaurant_guid, order_guid)
    return {
        "status": order["approvalStatus"],
        "fulfillment_status": order.get("fulfillmentStatus"),
        "voided": order["voided"]
    }
```

### Voice Flow Example

```
Agent: "Welcome to Joe's Pizza! What can I get for you today?"
Customer: "I'd like a large pepperoni pizza and a Caesar salad."

[Voice agent calls get_menu_items to validate items exist]

Agent: "Great! I have a large pepperoni pizza for $18.99 and a Caesar salad
        for $12.99. Would you like any modifications?"
Customer: "No, that's perfect."

Agent: "Your total is $31.98 plus tax. Can I get your name and phone number?"
Customer: "John Smith, 555-123-4567"

[Voice agent calls create_order with customer info]

Agent: "Perfect! Your order number is 42. It will be ready for pickup in
        about 20 minutes. Is there anything else I can help you with?"
```

### Handling Payment Options

**Pay-at-Pickup (Simplest for Voice):**
```python
# Simply don't include payments array
order["checks"][0]["payments"] = None  # or omit entirely
```

**Pre-paid (If you have payment processing):**
```python
order["checks"][0]["payments"] = [{
    "type": "OTHER",
    "amount": total_amount,
    "otherPayment": {"guid": your_payment_type_guid}
}]
```

</voice-integration>

---

## 11. Critical Limitations & Considerations

<considerations>

### API Limitations
- **No cash orders** via API
- **No Toast gift cards** via API
- **No Toast loyalty** via API
- **No service hours validation** - API creates orders even if restaurant closed
- **Max 1,000 selections** per order
- **Max 1 MB** request body size

### Order Confirmation
- `displayNumber` is **not guaranteed unique** across days
- Use `guid` (GUID) for reliable order tracking
- Consider using `tabName` for custom order identifiers

### Payment Timing
- Credit card authorization valid for **5 minutes** before applying to order
- Payment capture must occur within **7 days**

### Webhook Considerations
- PII **excluded** from webhook payloads
- Payloads can exceed **600KB**
- Must implement fallback polling

### Menu Sync
- Menu changes require cache invalidation
- Use `/menus/v2/metadata` endpoint to detect changes efficiently

### Security
- Never commit credentials to repositories
- Use environment variables or secret management
- Rotate credentials if compromised
- Contact Toast support immediately if credentials exposed

</considerations>

---

## 12. References

<references>

### Official Documentation
- [Toast Developer Portal](https://dev.toasttab.com/)
- [Developer Guide](https://doc.toasttab.com/doc/devguide/index.html)
- [API Reference](https://toastintegrations.redoc.ly/openapi/)
- [Orders API Overview](https://doc.toasttab.com/doc/devguide/portalOrdersApiOverview.html)

### API Endpoints
- [Creating Orders](https://doc.toasttab.com/doc/devguide/apiCreatingOrders.html)
- [Order Types & Dining Options](https://doc.toasttab.com/doc/devguide/apiOrderTypeDetails.html)
- [Order Schema Definition](https://doc.toasttab.com/openapi/orders/tag/Data-definitions/schema/Order/)
- [Post an Order](https://doc.toasttab.com/openapi/orders/operation/ordersPost/)
- [Get Order Prices](https://doc.toasttab.com/openapi/orders/operation/pricesPost/)

### Authentication
- [Authentication Guide](https://doc.toasttab.com/doc/devguide/authentication.html)
- [API Client Accounts](https://doc.toasttab.com/doc/devguide/apiClientAccounts.html)

### Payments
- [Alternative Payment Types](https://doc.toasttab.com/doc/devguide/apiCreatingAnOrderWithPaymentInformation.html)
- [Credit Card Payments](https://doc.toasttab.com/doc/devguide/authorizingCcPayments.html)
- [Adding Payments to Checks](https://doc.toasttab.com/doc/devguide/apiAddingPaymentsToACheck.html)

### Menus
- [Menus API Overview](https://doc.toasttab.com/doc/devguide/apiGettingMenuInformationFromTheMenusAPI.html)
- [Configuration API Menu Items](https://doc.toasttab.com/doc/devguide/menu_information_config_api.html)

### Webhooks
- [Orders Webhook](https://doc.toasttab.com/doc/devguide/devOrdersWebhookRef.html)
- [Webhook Basics](https://doc.toasttab.com/doc/devguide/apiWebhookBasics.html)
- [Guest Order Fulfillment Webhook](https://doc.toasttab.com/doc/devguide/apiGuestOrderFulfillmentStatusWebhook.html)

### Rate Limits & Best Practices
- [Rate Limiting](https://doc.toasttab.com/doc/devguide/apiRateLimiting.html)
- [Sandbox Environment](https://doc.toasttab.com/doc/devguide/apiEnvironments.html)
- [Integration Partnership Process](https://doc.toasttab.com/doc/devguide/integrationDevProcess.html)

### Integration Guides
- [Building an Online Ordering Integration](https://doc.toasttab.com/doc/cookbook/apiIntegrationChecklistOrdering.html)
- [How to Build a Toast Integration](https://doc.toasttab.com/doc/devguide/portalHowToBuildAToastIntegration.html)

</references>

---

## Research Metadata

<meta>
research-date: 2026-01-03
confidence-level: high
sources-validated: 15+
api-version: Orders API v2, Menus API v2/v3
last-api-update-checked: 2025-06-23 (tender API changes)
</meta>
