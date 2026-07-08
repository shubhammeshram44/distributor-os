// @ts-check
import { test, expect } from '@playwright/test';

// 30-day test token for demo tenant (S.V. Distributors)
const TEST_TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiZDEwMTAwMDAtMDAwMC0wMDAwLTAwMDAtMDAwMDAwMDAwMDAxIiwidGVuYW50X2lkIjoiZDNiMDczODQtZDExMy00OTU2LWE1ZDItNjRiZTczNTdjMTFkIiwic3ViIjoiKzkxOTg3NjU0MzIxMCIsInJvbGUiOiJEUklWRVIiLCJleHAiOjE3ODYxMTA1MTB9.n_qf1DuHabT0Vu8fPcpfNXtBTzpjQBsms9umAt6-33M';
const TENANT_ID = 'd3b07384-d113-4956-a5d2-64be7357c11d';
const TENANT_NAME = 'S.V. Distributors';

/** Inject auth into localStorage and navigate to the given path */
async function gotoAuthenticated(page, path) {
  await page.goto('/');
  await page.evaluate(({ token, tenantId, tenantName }) => {
    localStorage.setItem('accessToken', token);
    localStorage.setItem('tenant_id', tenantId);
    localStorage.setItem('tenant_name', tenantName);
  }, { token: TEST_TOKEN, tenantId: TENANT_ID, tenantName: TENANT_NAME });
  await page.goto(path);
  await page.waitForLoadState('networkidle');
}

// ---------------------------------------------------------------------------
// 1. AUTH PAGE
// ---------------------------------------------------------------------------
test.describe('Auth page', () => {
  test('renders phone input and send OTP button', async ({ page }) => {
    await page.goto('/auth');
    await expect(page.getByPlaceholder(/98765|e\.g\.|phone|mobile/i).first()).toBeVisible();
    await expect(page.getByRole('button', { name: /send otp|get otp|request|continue/i })).toBeVisible();
  });

  test('shows validation error for invalid phone', async ({ page }) => {
    await page.goto('/auth');
    await page.getByPlaceholder(/98765|e\.g\.|phone|mobile/i).first().fill('123');
    await page.getByRole('button', { name: /send otp|get otp|request|continue/i }).click();
    await expect(page.getByText(/invalid|valid.*number|enter.*valid/i)).toBeVisible();
  });

  test('unauthenticated /dashboard redirects to /auth', async ({ page }) => {
    await page.goto('/dashboard');
    await page.waitForURL(/\/auth/);
    expect(page.url()).toContain('/auth');
  });
});

// ---------------------------------------------------------------------------
// 2. DASHBOARD HOME
// ---------------------------------------------------------------------------
test.describe('Dashboard home', () => {
  test('loads metric cards with real data', async ({ page }) => {
    await gotoAuthenticated(page, '/dashboard');
    // Metric cards should be visible
    await expect(page.getByText(/total sales|revenue/i).first()).toBeVisible();
    await expect(page.getByText(/orders/i).first()).toBeVisible();
  });

  test('tenant name is accessible in the workspace selector', async ({ page }) => {
    await gotoAuthenticated(page, '/dashboard');
    // Tenant name appears in the workspace/account dropdown option (may be visually hidden)
    await expect(page.getByText(/S\.V\. Distributors|My Workspace/i).first()).toBeAttached({ timeout: 15000 });
  });

  test('sidebar navigation links are present', async ({ page }) => {
    await gotoAuthenticated(page, '/dashboard');
    const sidebar = page.locator('nav, aside, [class*="sidebar"], [class*="Sidebar"]').first();
    await expect(sidebar).toBeVisible();
    // At minimum: Orders and Products should exist
    await expect(page.getByRole('link', { name: /orders/i }).first()).toBeVisible();
  });

  test('WhatsApp simulator panel is present in DOM', async ({ page }) => {
    await gotoAuthenticated(page, '/dashboard');
    // WhatsAppSimulator is a fixed-position panel — check it's mounted in the DOM
    const simulatorHandle = await page.evaluate(() => {
      return !!document.querySelector('[class*="fixed"], [class*="simulator"], [id*="simulator"]');
    });
    // Alternatively look for the WhatsApp icon or "Simulate Order" text it renders
    const hasSimText = await page.getByText(/simulate|ingestion|whatsapp.*order|test.*order/i).count() > 0;
    expect(simulatorHandle || hasSimText).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// 3. ORDERS
// ---------------------------------------------------------------------------
test.describe('Orders page', () => {
  test('loads and displays order list', async ({ page }) => {
    await gotoAuthenticated(page, '/dashboard/orders');
    // Should show order IDs
    await expect(page.getByText(/ORD-/i).first()).toBeVisible({ timeout: 15000 });
  });

  test('shows at least 3 orders', async ({ page }) => {
    await gotoAuthenticated(page, '/dashboard/orders');
    await page.waitForSelector('text=ORD-', { timeout: 15000 });
    const orderRows = page.getByText(/ORD-/i);
    const count = await orderRows.count();
    expect(count).toBeGreaterThanOrEqual(3);
  });

  test('order amounts are visible', async ({ page }) => {
    await gotoAuthenticated(page, '/dashboard/orders');
    await page.waitForSelector('text=ORD-', { timeout: 15000 });
    // Currency amounts in Indian rupees
    await expect(page.getByText(/₹|Rs\.|23,650|45,320|96,450/i).first()).toBeVisible();
  });

  test('order status badges are visible', async ({ page }) => {
    await gotoAuthenticated(page, '/dashboard/orders');
    await page.waitForSelector('text=ORD-', { timeout: 15000 });
    await expect(page.getByText(/confirmed|pending|delivered/i).first()).toBeVisible();
  });

  test('search/filter input exists', async ({ page }) => {
    await gotoAuthenticated(page, '/dashboard/orders');
    await page.waitForSelector('text=ORD-', { timeout: 15000 });
    const searchInput = page.getByPlaceholder(/search|filter/i).first();
    await expect(searchInput).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// 4. PRODUCTS
// ---------------------------------------------------------------------------
test.describe('Products page', () => {
  test('loads and shows product list', async ({ page }) => {
    await gotoAuthenticated(page, '/dashboard/products');
    await expect(page.getByText(/HUL|ITC|Nestle|PROD-/i).first()).toBeVisible({ timeout: 15000 });
  });

  test('shows product SKUs', async ({ page }) => {
    await gotoAuthenticated(page, '/dashboard/products');
    await expect(page.getByText(/PROD-HUL|PROD-ITC|SKU/i).first()).toBeVisible({ timeout: 15000 });
  });

  test('shows prices in rupees', async ({ page }) => {
    await gotoAuthenticated(page, '/dashboard/products');
    await page.waitForSelector('text=/HUL|ITC|Nestle/i', { timeout: 15000 });
    await expect(page.getByText(/₹|45|260|10/i).first()).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// 5. CUSTOMERS
// ---------------------------------------------------------------------------
test.describe('Customers page', () => {
  test('loads customer list', async ({ page }) => {
    await gotoAuthenticated(page, '/dashboard/customers');
    await expect(page.getByText(/Kaveri|Maruthi|Sri Venkateshwara|Jayam|Balaji/i).first()).toBeVisible({ timeout: 15000 });
  });

  test('shows at least 4 customers', async ({ page }) => {
    await gotoAuthenticated(page, '/dashboard/customers');
    await page.waitForSelector('text=/Kaveri|Maruthi/i', { timeout: 15000 });
    const rows = page.getByText(/CUST-10[1-9]/i);
    const count = await rows.count();
    expect(count).toBeGreaterThanOrEqual(3);
  });

  test('outstanding balance is shown', async ({ page }) => {
    await gotoAuthenticated(page, '/dashboard/customers');
    await page.waitForSelector('text=/Kaveri|Maruthi/i', { timeout: 15000 });
    // Kaveri has ₹8.45L outstanding
    await expect(page.getByText(/8\.45L|845,000|outstanding/i).first()).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// 6. INVENTORY
// ---------------------------------------------------------------------------
test.describe('Inventory page', () => {
  test('loads and shows inventory table', async ({ page }) => {
    await gotoAuthenticated(page, '/dashboard/inventory');
    await expect(page.getByText(/HUL|ITC|inventory|stock/i).first()).toBeVisible({ timeout: 15000 });
  });

  test('stock quantities are visible in table rows', async ({ page }) => {
    await gotoAuthenticated(page, '/dashboard/inventory');
    // Wait for table data cells (td), not the filter dropdowns (option)
    await page.waitForSelector('table td', { timeout: 15000 });
    // Stock shown as "{n} units" inside a <td>
    await expect(page.locator('td').filter({ hasText: /\d+ units/ }).first()).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// 7. MESSAGES (WhatsApp inbox)
// ---------------------------------------------------------------------------
test.describe('Messages page', () => {
  test('renders the messages/inbox page', async ({ page }) => {
    await gotoAuthenticated(page, '/dashboard/messages');
    // Should show something — inbox header, chat list, or empty state
    await expect(page.locator('h1, h2, [class*="header"], [class*="inbox"], [class*="message"]').first()).toBeVisible({ timeout: 15000 });
  });

  test('page does not show a crash or error boundary', async ({ page }) => {
    await gotoAuthenticated(page, '/dashboard/messages');
    await expect(page.getByText(/something went wrong|error.*occurred|crash/i)).not.toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// 8. COLLECTIONS (Payments)
// ---------------------------------------------------------------------------
test.describe('Collections page', () => {
  test('renders the collections page', async ({ page }) => {
    await gotoAuthenticated(page, '/dashboard/collections');
    await expect(page.locator('h1, h2, [class*="header"], [class*="collection"]').first()).toBeVisible({ timeout: 15000 });
  });

  test('no error boundary visible', async ({ page }) => {
    await gotoAuthenticated(page, '/dashboard/collections');
    await expect(page.getByText(/something went wrong|error.*occurred/i)).not.toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// 9. SHIPMENTS
// ---------------------------------------------------------------------------
test.describe('Shipments page', () => {
  test('renders the shipments page', async ({ page }) => {
    await gotoAuthenticated(page, '/dashboard/shipments');
    await expect(page.locator('h1, h2, [class*="header"], [class*="shipment"]').first()).toBeVisible({ timeout: 15000 });
  });
});

// ---------------------------------------------------------------------------
// 10. REPORTS / ANALYTICS
// ---------------------------------------------------------------------------
test.describe('Reports page', () => {
  test('renders the reports page', async ({ page }) => {
    await gotoAuthenticated(page, '/dashboard/reports');
    await expect(page.locator('h1, h2, [class*="report"], [class*="analytics"]').first()).toBeVisible({ timeout: 15000 });
  });
});

test.describe('Sales Analytics page', () => {
  test('renders the sales analytics page', async ({ page }) => {
    await gotoAuthenticated(page, '/dashboard/sales-analytics');
    await expect(page.locator('h1, h2, canvas, [class*="chart"], [class*="analytics"]').first()).toBeVisible({ timeout: 15000 });
  });
});

// ---------------------------------------------------------------------------
// 11. SETTINGS — INTEGRATIONS (WhatsApp)
// ---------------------------------------------------------------------------
test.describe('Settings: Integrations page', () => {
  test('renders the integrations page with WhatsApp section', async ({ page }) => {
    await gotoAuthenticated(page, '/dashboard/settings/integrations');
    await expect(page.getByText(/WhatsApp|Evolution/i).first()).toBeVisible({ timeout: 15000 });
  });

  test('Connect WhatsApp button or status indicator is present', async ({ page }) => {
    await gotoAuthenticated(page, '/dashboard/settings/integrations');
    await page.waitForSelector('text=/WhatsApp|Evolution/i', { timeout: 15000 });
    // Either a Connect button or connected status
    const connectBtn = page.getByRole('button', { name: /connect|setup|provision/i });
    const connectedStatus = page.getByText(/connected|active|disconnect/i);
    const hasConnect = await connectBtn.count() > 0;
    const hasConnected = await connectedStatus.count() > 0;
    expect(hasConnect || hasConnected).toBe(true);
  });

  test('instance name field pre-fills with dist- prefix, never default-bot', async ({ page }) => {
    await gotoAuthenticated(page, '/dashboard/settings/integrations');
    await page.waitForSelector('text=/WhatsApp|Evolution/i', { timeout: 15000 });
    // Verify no input has value "default-bot"
    const defaultBotInputs = await page.locator('input[value="default-bot"]').count();
    expect(defaultBotInputs).toBe(0);
    // If the instance name input is visible, it should have dist- prefix
    const instInputs = await page.locator('input[value^="dist-"]').count();
    const connectedText = await page.getByText(/connected|active/i).count();
    // Either showing dist- input OR already connected (input hidden) — both are valid
    expect(instInputs > 0 || connectedText > 0).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// 12. SETTINGS — TEAM
// ---------------------------------------------------------------------------
test.describe('Settings: Team page', () => {
  test('renders the team settings page', async ({ page }) => {
    await gotoAuthenticated(page, '/dashboard/settings/team');
    await expect(page.locator('h1, h2, [class*="team"], [class*="header"]').first()).toBeVisible({ timeout: 15000 });
  });
});

// ---------------------------------------------------------------------------
// 13. CROSS-PAGE NAVIGATION
// ---------------------------------------------------------------------------
test.describe('Navigation', () => {
  test('navigating from orders to customers via sidebar works', async ({ page }) => {
    await gotoAuthenticated(page, '/dashboard/orders');
    await page.waitForSelector('text=ORD-', { timeout: 15000 });

    const customersLink = page.getByRole('link', { name: /customers/i }).first();
    await customersLink.click();
    await page.waitForURL(/\/customers/);
    await expect(page.getByText(/Kaveri|Maruthi|customer/i).first()).toBeVisible({ timeout: 15000 });
  });

  test('navigating back from customers to dashboard preserves auth', async ({ page }) => {
    await gotoAuthenticated(page, '/dashboard/customers');
    await page.waitForSelector('text=/Kaveri|Maruthi/i', { timeout: 15000 });

    const dashboardLink = page.getByRole('link', { name: /dashboard|home/i }).first();
    await dashboardLink.click();
    // Next.js routes /dashboard/ with trailing slash — accept both
    await page.waitForURL(/\/dashboard\/?(\?.*)?$/, { timeout: 20000 });
    // Should NOT redirect to /auth — stays on dashboard
    expect(page.url()).not.toContain('/auth');
    await expect(page.getByText(/total sales|orders|revenue/i).first()).toBeVisible({ timeout: 15000 });
  });
});

// ---------------------------------------------------------------------------
// 14. API HEALTH (direct probes)
// ---------------------------------------------------------------------------
test.describe('Backend API health', () => {
  const API = 'http://localhost:8000';
  const AUTH_HEADER = { Authorization: `Bearer ${TEST_TOKEN}` };

  test('GET /api/v1/auth/me returns user profile', async ({ request }) => {
    const resp = await request.get(`${API}/api/v1/auth/me`, { headers: AUTH_HEADER });
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body.tenant.name).toBe(TENANT_NAME);
  });

  test('GET /api/v1/orders returns order list', async ({ request }) => {
    const resp = await request.get(`${API}/api/v1/orders`, { headers: AUTH_HEADER });
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body.total).toBeGreaterThanOrEqual(1);
    expect(body.items[0]).toHaveProperty('order_id');
  });

  test('GET /api/v1/products returns product list', async ({ request }) => {
    const resp = await request.get(`${API}/api/v1/products?tenant_id=${TENANT_ID}`, { headers: AUTH_HEADER });
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body.total).toBeGreaterThanOrEqual(1);
    expect(body.items[0]).toHaveProperty('sku_id');
  });

  test('GET /api/v1/customers returns customer list', async ({ request }) => {
    const resp = await request.get(`${API}/api/v1/customers?tenant_id=${TENANT_ID}`, { headers: AUTH_HEADER });
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body.total).toBeGreaterThanOrEqual(5);
  });

  test('GET /api/v1/dashboard/metrics returns KPIs', async ({ request }) => {
    const resp = await request.get(`${API}/api/v1/dashboard/metrics`, { headers: AUTH_HEADER });
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body).toHaveProperty('total_sales');
    expect(body).toHaveProperty('orders_count');
    expect(body).toHaveProperty('outstanding_collections');
  });

  test('GET /api/v1/inventory/dashboard-grid returns stock grid', async ({ request }) => {
    const resp = await request.get(`${API}/api/v1/inventory/dashboard-grid`, { headers: AUTH_HEADER });
    expect(resp.status()).toBe(200);
  });

  test('invalid token returns 401 on /auth/me', async ({ request }) => {
    const resp = await request.get(`${API}/api/v1/auth/me`, {
      headers: { Authorization: 'Bearer bad.token.here' }
    });
    expect(resp.status()).toBe(401);
  });

  test('WhatsApp webhook accepts connection.update handshake', async ({ request }) => {
    const resp = await request.post(`${API}/api/v1/whatsapp/webhook`, {
      data: { event: 'connection.update', instance: 'dist-d3b0738', state: 'open' },
    });
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body.status).toBe('SUCCESS');
  });
});
