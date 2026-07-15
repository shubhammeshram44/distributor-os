"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { Inter, Plus_Jakarta_Sans } from 'next/font/google';

const inter = Inter({ subsets: ['latin'], variable: '--font-inter' });
const plusJakartaSans = Plus_Jakarta_Sans({ subsets: ['latin'], variable: '--font-plus-jakarta-sans' });

const TOP_PRODUCTS = [
  { name: 'Parle-G', pct: '25%', width: '25%' },
  { name: 'Maggi', pct: '18%', width: '18%' },
  { name: 'Surf Excel', pct: '14%', width: '14%' }
];

const STATS = [
  { value: '4+ Hours', label: 'Saved every day on order entry' },
  { value: '₹20,000+', label: 'Monthly clerk cost replaced' },
  { value: '2x Faster', label: 'Payment collection with automated reminders' },
  { value: '100% Visibility', label: 'Of your business, anytime, anywhere' },
  { value: 'Zero Data Entry', label: 'No manual typing. No human errors.' }
];

const TRUSTED_LOGOS = ['Prakash Distributors', 'Shree Balaji Distributors', 'Gupta Traders', 'Mahalaxmi Distributors', '+50 more'];

const PROBLEMS = [
  { icon: '💬', title: 'Orders lost in WhatsApp chats', body: 'Retailer messages get buried and missed entirely' },
  { icon: '🧾', title: 'Manual billing wastes hours', body: 'Creating invoices by hand, every day, for every order' },
  { icon: '📞', title: 'Chasing payments is exhausting', body: "Calling retailers again and again just to collect what you're owed" }
];

const PILLARS = [
  { icon: '📉', title: 'Lost Sales Intelligence', body: "Know every order you couldn't fulfil. Recover lost revenue." },
  { icon: '💰', title: 'Collections Intelligence', body: 'Know who to call today. Collect payments 2x faster.' },
  { icon: '📦', title: 'Inventory Intelligence', body: 'Never run out of stock. Never overstock again.' },
  { icon: '👥', title: 'Customer Intelligence', body: 'Identify inactive retailers and grow your customer base.' },
  { icon: '⚡', title: 'Business Health Score', body: 'One score that shows how your business is performing.' }
];

const STEPS = [
  { icon: '💬', title: 'Orders on WhatsApp', body: 'Retailers send orders as they always do.' },
  { icon: '🤖', title: 'AI Reads & Understands', body: 'Our AI understands, validates and creates clean orders.' },
  { icon: '✅', title: 'You Review & Confirm', body: 'Review once a day and confirm all orders.' },
  { icon: '📄', title: 'Invoices & Dispatch', body: 'Invoices are generated. Goods are dispatched.' },
  { icon: '💳', title: 'Payments & Collections', body: 'Record payments and automate follow-ups.' },
  { icon: '📈', title: 'Insights & Growth', body: 'Get AI insights and grow your business.' }
];

const AI_ITEMS = [
  { name: 'Surf Excel (1kg)', qty: '5 BOX' },
  { name: 'Wheel (500g)', qty: '2 BOX' },
  { name: 'Vim (500ml)', qty: '1 BOX' }
];

const AI_CAPABILITIES = [
  { icon: '🎙️', text: 'Understands text, voice, images and even messy orders' },
  { icon: '🔗', text: 'Maps to your products automatically' },
  { icon: '📊', text: 'Checks stock & credit in real-time' },
  { icon: '⚠️', text: 'Flags issues before you confirm' }
];

const PLANS = [
  { name: 'Free Trial', price: '₹0', period: '/ 15 days', popular: false, shadow: '0 4px 24px rgba(0,0,0,0.08)', border: '1px solid #E2E8F0',
    features: ['All features included', 'No credit card needed', 'Full WhatsApp AI parsing', 'Cancel anytime'],
    ctaBg: 'transparent', ctaColor: '#4F46E5', ctaBorder: '1px solid #4F46E5', cta: 'Start Free Trial' },
  { name: 'Growth', price: '₹899', period: '/month', popular: true, shadow: '0 12px 32px rgba(79,70,229,0.18)', border: '2px solid #4F46E5',
    features: ['Up to 500 orders/month', '1 WhatsApp number', 'Auto invoicing & payments', 'Collections reminders', 'Email support'],
    ctaBg: '#4F46E5', ctaColor: '#fff', ctaBorder: 'none', cta: 'Start Free Trial' },
  { name: 'Pro', price: '₹1,499', period: '/month', popular: false, shadow: '0 4px 24px rgba(0,0,0,0.08)', border: '1px solid #E2E8F0',
    features: ['Unlimited orders', '3 WhatsApp numbers', 'Priority support + dedicated onboarding', 'Tally XML export', 'Business Health Score'],
    ctaBg: 'transparent', ctaColor: '#4F46E5', ctaBorder: '1px solid #4F46E5', cta: 'Start Free Trial' }
];

const FAQ_DATA = [
  { q: 'Do my retailers need to download an app?', a: 'No. They WhatsApp you exactly as they do today. Nothing changes for them.' },
  { q: 'Will this affect my Tally or Marg?', a: "No. We don't touch your books. We handle everything before an invoice exists. Your CA won't even know we exist." },
  { q: 'What if the AI misreads an order?', a: 'Every order goes into a review queue before confirmation. You always have final approval.' },
  { q: 'What languages does it understand?', a: 'Hindi, English, Hinglish, and common Indian shorthand — "bhaiya", "bhejna", mixed scripts — all understood.' },
  { q: 'What happens if WhatsApp disconnects?', a: 'You get an instant alert on your dashboard and can reconnect in one click. Orders continue via your existing manual process as backup.' }
];

export default function MarketingPage() {
  const [faqOpen, setFaqOpen] = useState(0);

  useEffect(() => {
    document.title = "DistributorOS — WhatsApp Order Management for Distributors";

    const els = document.querySelectorAll('[data-fade]');
    const obs = new IntersectionObserver((entries) => {
      entries.forEach(e => { if (e.isIntersecting) e.target.classList.add('in'); });
    }, { threshold: 0.1 });
    els.forEach(el => obs.observe(el));
    return () => obs.disconnect();
  }, []);

  const topProducts = TOP_PRODUCTS;
  const stats = STATS;
  const trustedLogos = TRUSTED_LOGOS;
  const problems = PROBLEMS;
  const pillars = PILLARS;
  const steps = STEPS;
  const aiItems = AI_ITEMS;
  const aiCapabilities = AI_CAPABILITIES;
  const plans = PLANS;

  const faqs = FAQ_DATA.map((f, i) => ({
    q: f.q,
    a: f.a,
    open: faqOpen === i,
    symbol: faqOpen === i ? '−' : '+',
    toggle: () => setFaqOpen(faqOpen === i ? -1 : i)
  }));

  return (


<div className={`${inter.variable} ${plusJakartaSans.variable}`} style={{background: '#FFFFFF', overflowX: 'hidden'}}>
  <style dangerouslySetInnerHTML={{ __html: `
    body {
      margin: 0;
      font-family: var(--font-inter), sans-serif;
      -webkit-font-smoothing: antialiased;
    }
    a {
      color: #4F46E5;
      text-decoration: none;
    }
    a:hover {
      color: #4338CA;
    }
    h1, h2, h3, .disp {
      font-family: var(--font-plus-jakarta-sans), sans-serif;
    }
    [data-fade] {
      opacity: 0;
      transform: translateY(16px);
      transition: opacity .6s ease, transform .6s ease;
    }
    [data-fade].in {
      opacity: 1;
      transform: translateY(0);
    }
    @keyframes spin {
      from { stroke-dashoffset: 0; }
      to { stroke-dashoffset: 0; }
    }
    ::selection {
      background: #C7D2FE;
    }
    @media (max-width: 900px) {
      [data-nav-links="1"] { display: none !important; }
      [data-hero-grid="1"] { grid-template-columns: 1fr !important; }
      [data-stats-grid="1"] { grid-template-columns: repeat(2, 1fr) !important; }
      [data-problem-grid="1"] { grid-template-columns: 1fr !important; }
      [data-pillars-grid="1"] { grid-template-columns: repeat(2, 1fr) !important; }
      [data-steps-grid="1"] { grid-template-columns: repeat(2, 1fr) !important; }
      [data-steps-line="1"] { display: none !important; }
      [data-ai-grid="1"] { grid-template-columns: 1fr !important; }
      [data-pricing-grid="1"] { grid-template-columns: 1fr !important; }
      [data-footer-grid="1"] { grid-template-columns: 1fr 1fr !important; }
    }
  ` }} />

{/* NAV */}
<nav style={{position: 'sticky', top: 0, zIndex: 50, background: 'rgba(255,255,255,0.92)', backdropFilter: 'blur(10px)', borderBottom: '1px solid #E2E8F0'}}>
  <div style={{maxWidth: 1200, margin: '0 auto', padding: '16px 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between'}}>
    <div className="disp" style={{fontSize: 22, fontWeight: 800, color: '#0F172A'}}>Distributor<span style={{color: '#4F46E5'}}>OS</span></div>
    <div style={{display: 'flex', alignItems: 'center', gap: 36}} data-nav-links="1">
      <a href="#features" style={{color: '#334155', fontWeight: 600, fontSize: 15}}>Features</a>
      <a href="#how-it-works" style={{color: '#334155', fontWeight: 600, fontSize: 15}}>How It Works</a>
      <a href="#pricing" style={{color: '#334155', fontWeight: 600, fontSize: 15}}>Pricing</a>
    </div>
    <div style={{display: 'flex', alignItems: 'center', gap: 12}}>
      <Link href="/auth" style={{textDecoration: 'none'}}><button style={{background: 'transparent', border: '1px solid #CBD5E1', color: '#334155', fontWeight: 600, fontSize: 14, padding: '10px 20px', borderRadius: 10, cursor: 'pointer', fontFamily: '\'Inter\',sans-serif', whiteSpace: 'nowrap', flexShrink: 0}}>Log In</button></Link>
      <Link href="/auth" style={{textDecoration: 'none'}}><button style={{background: '#4F46E5', border: 'none', color: '#fff', fontWeight: 700, fontSize: 14, padding: '10px 22px', borderRadius: 10, cursor: 'pointer', boxShadow: '0 4px 14px rgba(79,70,229,0.35)', fontFamily: '\'Inter\',sans-serif', whiteSpace: 'nowrap', flexShrink: 0}}>Start Free Trial</button></Link>
    </div>
  </div>
</nav>

{/* HERO */}
<section data-hero-grid="1" style={{maxWidth: 1200, margin: '0 auto', padding: '40px 24px 64px', display: 'grid', gridTemplateColumns: '1.05fr 1fr', gap: 56, alignItems: 'center'}}>
  <div>
    <div style={{display: 'inline-flex', alignItems: 'center', gap: 8, background: '#EEF2FF', color: '#4F46E5', fontWeight: 700, fontSize: 13, padding: '8px 16px', borderRadius: 999, marginBottom: 24}}>Built for Indian Distributors 🇮🇳</div>
    <h1 className="disp" style={{fontSize: 52, lineHeight: 1.12, fontWeight: 800, color: '#0F172A', margin: '0 0 24px', letterSpacing: '-0.02em'}}>Run your distribution business on autopilot.</h1>
    <p style={{fontSize: 18, lineHeight: 1.6, color: '#475569', margin: '0 0 32px', maxWidth: 520}}>Retailers WhatsApp you orders. We turn them into invoices, inventory updates, and payment links — automatically. Keep Tally. Keep WhatsApp. Add zero new habits.</p>
    <div style={{display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 16}}>
      <Link href="/auth" style={{textDecoration: 'none'}}><button style={{background: '#4F46E5', border: 'none', color: '#fff', fontWeight: 700, fontSize: 16, padding: '16px 28px', borderRadius: 12, cursor: 'pointer', boxShadow: '0 8px 24px rgba(79,70,229,0.35)', fontFamily: '\'Inter\',sans-serif'}}>Start Free Trial →</button></Link>
      <a href="#how-it-works" style={{textDecoration: 'none'}}><button style={{background: 'transparent', border: '1px solid #CBD5E1', color: '#0F172A', fontWeight: 700, fontSize: 16, padding: '16px 28px', borderRadius: 12, cursor: 'pointer', fontFamily: '\'Inter\',sans-serif'}}>See How It Works</button></a>
    </div>
    <p style={{fontSize: 14, color: '#94A3B8', margin: 0}}>No credit card needed · 15-day free trial · Setup in 10 minutes</p>
  </div>

  <div style={{position: 'relative'}}>
    <div style={{position: 'absolute', inset: -40, background: 'radial-gradient(circle at 30% 20%,rgba(79,70,229,0.25),transparent 60%),radial-gradient(circle at 80% 80%,rgba(16,185,129,0.2),transparent 60%)', filter: 'blur(20px)'}}></div>
    <div style={{position: 'relative', background: '#0F172A', borderRadius: 20, padding: 24, boxShadow: '0 30px 60px rgba(15,23,42,0.35)', color: '#fff'}}>
      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20}}>
        <div>
          <div style={{fontWeight: 700, fontSize: 15}}>Raj Kumar</div>
          <div style={{fontSize: 12, color: '#94A3B8'}}>Shree Balaji Distributors</div>
        </div>
        <div style={{width: 36, height: 36, borderRadius: '50%', background: '#334155'}}></div>
      </div>
      <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16}}>
        <div style={{background: '#1E293B', borderRadius: 12, padding: 14}}>
          <div style={{fontSize: 11, color: '#94A3B8', marginBottom: 4}}>Orders Received</div>
          <div style={{fontSize: 20, fontWeight: 800}}>128</div>
        </div>
        <div style={{background: '#1E293B', borderRadius: 12, padding: 14}}>
          <div style={{fontSize: 11, color: '#94A3B8', marginBottom: 4}}>Sales Today</div>
          <div style={{fontSize: 20, fontWeight: 800, color: '#10B981'}}>₹4,52,300</div>
        </div>
        <div style={{background: '#1E293B', borderRadius: 12, padding: 14}}>
          <div style={{fontSize: 11, color: '#94A3B8', marginBottom: 4}}>Outstanding</div>
          <div style={{fontSize: 20, fontWeight: 800}}>₹12,45,000</div>
        </div>
        <div style={{background: '#1E293B', borderRadius: 12, padding: 14}}>
          <div style={{fontSize: 11, color: '#94A3B8', marginBottom: 4}}>Collections Today</div>
          <div style={{fontSize: 20, fontWeight: 800, color: '#10B981'}}>₹1,25,000</div>
        </div>
      </div>
      <div style={{background: '#1E293B', borderRadius: 12, padding: 16, marginBottom: 12}}>
        <div style={{fontSize: 12, color: '#94A3B8', marginBottom: 10}}>Orders by Source</div>
        <div style={{display: 'flex', alignItems: 'center', gap: 16}}>
          <div style={{width: 64, height: 64, borderRadius: '50%', background: 'conic-gradient(#10B981 0% 65%,#4F46E5 65% 85%,#F59E0B 85% 95%,#64748B 95% 100%)', flexShrink: 0}}></div>
          <div style={{display: 'flex', flexDirection: 'column', gap: 4, fontSize: 11}}>
            <div><span style={{color: '#10B981'}}>●</span> WhatsApp 65%</div>
            <div><span style={{color: '#4F46E5'}}>●</span> Sales App 20%</div>
            <div><span style={{color: '#F59E0B'}}>●</span> Phone 10%</div>
            <div><span style={{color: '#64748B'}}>●</span> Others 5%</div>
          </div>
        </div>
      </div>
      <div style={{background: '#1E293B', borderRadius: 12, padding: 16, marginBottom: 12}}>
        <div style={{fontSize: 12, color: '#94A3B8', marginBottom: 10}}>Top Products</div>
        {topProducts && topProducts.map((p, i) => (<React.Fragment key={i}>
          <div style={{display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8, fontSize: 12}}>
            <div style={{width: 80}}>{ p.name }</div>
            <div style={{flex: 1, height: 6, background: '#334155', borderRadius: 4, overflow: 'hidden'}}><div style={{height: '100%', background: '#10B981', width: p.width}}></div></div>
            <div style={{color: '#94A3B8'}}>{ p.pct }</div>
          </div>
        </React.Fragment>))}
      </div>
      <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10}}>
        <div style={{background: '#1E293B', borderRadius: 10, padding: '10px 12px'}}>
          <div style={{fontSize: 10, color: '#94A3B8'}}>Inactive Retailers</div>
          <div style={{fontSize: 15, fontWeight: 700, color: '#F87171'}}>23</div>
        </div>
        <div style={{background: '#1E293B', borderRadius: 10, padding: '10px 12px'}}>
          <div style={{fontSize: 10, color: '#94A3B8'}}>Payment Due Today</div>
          <div style={{fontSize: 15, fontWeight: 700, color: '#F59E0B'}}>₹73,000</div>
        </div>
        <div style={{background: '#1E293B', borderRadius: 10, padding: '10px 12px'}}>
          <div style={{fontSize: 10, color: '#94A3B8'}}>Stock Out Risk</div>
          <div style={{fontSize: 15, fontWeight: 700, color: '#F87171'}}>8</div>
        </div>
        <div style={{background: '#1E293B', borderRadius: 10, padding: '10px 12px'}}>
          <div style={{fontSize: 10, color: '#94A3B8'}}>Lost Sales This Month</div>
          <div style={{fontSize: 15, fontWeight: 700, color: '#F87171'}}>₹2,87,000</div>
        </div>
      </div>
    </div>
  </div>
</section>

{/* TRUSTED BY */}
<section style={{maxWidth: 1200, margin: '0 auto', padding: '32px 24px 64px'}}>
  <p style={{textAlign: 'center', color: '#94A3B8', fontSize: 13, fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase', margin: '0 0 24px'}}>Trusted by distributors across India</p>
  <div style={{display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 40, flexWrap: 'wrap'}}>
    {trustedLogos && trustedLogos.map((l, i) => (<React.Fragment key={i}>
      <div style={{color: '#64748B', fontWeight: 700, fontSize: 15, fontFamily: '\'Plus Jakarta Sans\',sans-serif'}}>{ l }</div>
    </React.Fragment>))}
  </div>
</section>

{/* STATS BAR */}
<section style={{background: '#F1F5F9', padding: '56px 24px'}}>
  <div data-stats-grid="1" style={{maxWidth: 1200, margin: '0 auto', display: 'grid', gridTemplateColumns: 'repeat(5,1fr)', gap: 24}}>
    {stats && stats.map((s, i) => (<React.Fragment key={i}>
      <div style={{textAlign: 'center'}}>
        <div className="disp" style={{fontSize: 28, fontWeight: 800, color: '#0F172A', marginBottom: 6}}>{ s.value }</div>
        <div style={{fontSize: 13, color: '#64748B', lineHeight: 1.4}}>{ s.label }</div>
      </div>
    </React.Fragment>))}
  </div>
  <p style={{textAlign: 'center', color: '#94A3B8', fontSize: 12, margin: '32px 0 0'}}>*Based on industry benchmarks for mid-size distributors handling 50+ orders/day.</p>
</section>

{/* PROBLEM */}
<section style={{maxWidth: 1200, margin: '0 auto', padding: '96px 24px'}}>
  <h2 className="disp" style={{fontSize: 38, fontWeight: 800, color: '#0F172A', textAlign: 'center', margin: '0 0 56px', letterSpacing: '-0.01em'}}>Running orders on WhatsApp alone is chaos.</h2>
  <div data-problem-grid="1" style={{display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 24}}>
    {problems && problems.map((pr, i) => (<React.Fragment key={i}>
      <div style={{background: '#fff', borderRadius: 16, padding: 32, boxShadow: '0 4px 24px rgba(0,0,0,0.08)'}}>
        <div style={{fontSize: 32, marginBottom: 16}}>{ pr.icon }</div>
        <h3 style={{fontSize: 18, fontWeight: 700, color: '#0F172A', margin: '0 0 8px'}}>{ pr.title }</h3>
        <p style={{fontSize: 15, color: '#475569', lineHeight: 1.6, margin: 0}}>{ pr.body }</p>
      </div>
    </React.Fragment>))}
  </div>
</section>

{/* INTELLIGENCE PILLARS */}
<section id="features" style={{background: '#F8FAFC', padding: '96px 24px'}}>
  <div style={{maxWidth: 1200, margin: '0 auto'}}>
    <h2 className="disp" style={{fontSize: 38, fontWeight: 800, color: '#0F172A', textAlign: 'center', margin: '0 0 56px', letterSpacing: '-0.01em'}}>Get complete visibility. Take the right actions.</h2>
    <div data-pillars-grid="1" style={{display: 'grid', gridTemplateColumns: 'repeat(5,1fr)', gap: 20}}>
      {pillars && pillars.map((pi, i) => (<React.Fragment key={i}>
        <div style={{background: '#fff', borderRadius: 16, padding: '24px 20px', boxShadow: '0 4px 24px rgba(0,0,0,0.06)', textAlign: 'center'}}>
          <div style={{fontSize: 28, marginBottom: 14}}>{ pi.icon }</div>
          <h3 style={{fontSize: 15, fontWeight: 700, color: '#0F172A', margin: '0 0 8px'}}>{ pi.title }</h3>
          <p style={{fontSize: 13, color: '#64748B', lineHeight: 1.5, margin: 0}}>{ pi.body }</p>
        </div>
      </React.Fragment>))}
    </div>
  </div>
</section>

{/* HOW IT WORKS */}
<section id="how-it-works" style={{maxWidth: 1200, margin: '0 auto', padding: '96px 24px'}}>
  <h2 className="disp" style={{fontSize: 38, fontWeight: 800, color: '#0F172A', textAlign: 'center', margin: '0 0 64px', letterSpacing: '-0.01em'}}>How DistributorOS Works</h2>
  <div data-steps-grid="1" style={{position: 'relative', display: 'grid', gridTemplateColumns: 'repeat(6,1fr)', gap: 16}}>
    <div data-steps-line="1" style={{position: 'absolute', top: 28, left: '8%', right: '8%', height: 0, borderTop: '2px dashed #CBD5E1', zIndex: 0}}></div>
    {steps && steps.map((st, i) => (<React.Fragment key={i}>
      <div style={{position: 'relative', zIndex: 1, textAlign: 'center'}}>
        <div style={{width: 56, height: 56, borderRadius: '50%', background: '#4F46E5', color: '#fff', fontSize: 22, display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px', boxShadow: '0 6px 16px rgba(79,70,229,0.3)'}}>{ st.icon }</div>
        <h3 style={{fontSize: 14, fontWeight: 700, color: '#0F172A', margin: '0 0 6px'}}>{ st.title }</h3>
        <p style={{fontSize: 12, color: '#64748B', lineHeight: 1.5, margin: 0}}>{ st.body }</p>
      </div>
    </React.Fragment>))}
  </div>
</section>

{/* AI SECTION */}
<section style={{background: '#F8FAFC', padding: '96px 24px'}}>
  <div style={{maxWidth: 1200, margin: '0 auto'}}>
    <h2 className="disp" style={{fontSize: 38, fontWeight: 800, color: '#0F172A', textAlign: 'center', margin: '0 0 64px', letterSpacing: '-0.01em'}}>AI that understands the way you do business.</h2>
    <div data-ai-grid="1" style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 48, alignItems: 'center'}}>
      <div>
        <div style={{display: 'flex', alignItems: 'flex-end', gap: 12, marginBottom: 24}}>
          <div style={{background: '#DCF8C6', borderRadius: '12px 12px 12px 2px', padding: '14px 18px', maxWidth: 320, boxShadow: '0 4px 12px rgba(0,0,0,0.06)'}}>
            <p style={{margin: 0, fontSize: 14, color: '#0F172A', lineHeight: 1.5}}>Bhai, 5 box Surf Excel, 2 box Wheel, 1 box Vim. Kal delivery kar dena.</p>
            <div style={{fontSize: 11, color: '#64748B', textAlign: 'right', marginTop: 6}}>11:30 AM</div>
          </div>
        </div>
        <div style={{textAlign: 'center', fontSize: 24, color: '#94A3B8', marginBottom: 24}}>↓</div>
        <div style={{background: '#0F172A', borderRadius: 16, padding: 24, color: '#fff', boxShadow: '0 20px 40px rgba(15,23,42,0.25)'}}>
          <div style={{fontSize: 12, color: '#10B981', fontWeight: 700, marginBottom: 12}}>DistributorOS AI Output</div>
          {aiItems && aiItems.map((ai, i) => (<React.Fragment key={i}>
            <div style={{display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid #1E293B', fontSize: 14}}>
              <span>{ ai.name }</span><span style={{fontWeight: 700}}>{ ai.qty }</span>
            </div>
          </React.Fragment>))}
          <div style={{display: 'flex', gap: 16, marginTop: 14, fontSize: 12, color: '#94A3B8'}}>
            <span>Delivery: Tomorrow</span><span>Priority: Normal</span>
          </div>
        </div>
      </div>
      <div style={{display: 'flex', flexDirection: 'column', gap: 24}}>
        {aiCapabilities && aiCapabilities.map((c, i) => (<React.Fragment key={i}>
          <div style={{display: 'flex', gap: 16, alignItems: 'flex-start'}}>
            <div style={{fontSize: 22, flexShrink: 0}}>{ c.icon }</div>
            <p style={{margin: 0, fontSize: 16, color: '#334155', lineHeight: 1.5, fontWeight: 500}}>{ c.text }</p>
          </div>
        </React.Fragment>))}
      </div>
    </div>
  </div>
</section>

{/* PRICING */}
<section id="pricing" style={{maxWidth: 1200, margin: '0 auto', padding: '96px 24px'}}>
  <h2 className="disp" style={{fontSize: 38, fontWeight: 800, color: '#0F172A', textAlign: 'center', margin: '0 0 12px', letterSpacing: '-0.01em'}}>Simple pricing, no surprises</h2>
  <div data-pricing-grid="1" style={{display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 24, marginTop: 56, alignItems: 'stretch'}}>
    {plans && plans.map((pl, i) => (<React.Fragment key={i}>
      <div style={{background: '#fff', borderRadius: 16, padding: 32, display: 'flex', flexDirection: 'column', boxShadow: pl.shadow, border: pl.border, position: 'relative'}}>
        {pl.popular && (<React.Fragment>
          <div style={{position: 'absolute', top: -14, left: '50%', transform: 'translateX(-50%)', background: '#4F46E5', color: '#fff', fontSize: 12, fontWeight: 700, padding: '6px 16px', borderRadius: 999}}>⭐ MOST POPULAR</div>
        </React.Fragment>)}
        <h3 style={{fontSize: 18, fontWeight: 700, color: '#0F172A', margin: '8px 0 4px'}}>{ pl.name }</h3>
        <div style={{marginBottom: 20}}>
          <span className="disp" style={{fontSize: 32, fontWeight: 800, color: '#0F172A'}}>{ pl.price }</span>
          <span style={{fontSize: 14, color: '#94A3B8'}}>{ pl.period }</span>
        </div>
        <div style={{display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 28, flex: 1}}>
          {pl.features && pl.features.map((f, i) => (<React.Fragment key={i}>
            <div style={{display: 'flex', gap: 8, alignItems: 'flex-start', fontSize: 14, color: '#475569'}}><span style={{color: '#10B981', fontWeight: 700}}>✓</span>{ f }</div>
          </React.Fragment>))}
        </div>
        <Link href="/auth" style={{textDecoration: 'none', display: 'block', width: '100%'}}><button style={{background: pl.ctaBg, color: pl.ctaColor, border: pl.ctaBorder, width: '100%', fontWeight: 700, fontSize: 15, padding: 14, borderRadius: 10, cursor: 'pointer', fontFamily: '\'Inter\',sans-serif'}}>{ pl.cta }</button></Link>
      </div>
    </React.Fragment>))}
  </div>
  <div style={{textAlign: 'center', marginTop: 40}}>
    <p style={{color: '#64748B', fontSize: 14, margin: '0 0 4px'}}>Not sure which plan? Start with the free trial. Upgrade anytime.</p>
    <p style={{color: '#64748B', fontSize: 14, margin: 0}}>Keep your Tally. Keep your WhatsApp. DistributorOS works alongside both.</p>
  </div>
</section>

{/* FAQ */}
<section style={{background: '#F8FAFC', padding: '96px 24px'}}>
  <div style={{maxWidth: 800, margin: '0 auto'}}>
    <h2 className="disp" style={{fontSize: 38, fontWeight: 800, color: '#0F172A', textAlign: 'center', margin: '0 0 48px', letterSpacing: '-0.01em'}}>Frequently Asked Questions</h2>
    {faqs && faqs.map((fq, i) => (<React.Fragment key={i}>
      <div style={{background: '#fff', borderRadius: 14, marginBottom: 14, boxShadow: '0 2px 12px rgba(0,0,0,0.05)', overflow: 'hidden'}}>
        <div onClick={ fq.toggle } style={{padding: '20px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer'}}>
          <h3 style={{fontSize: 16, fontWeight: 700, color: '#0F172A', margin: 0}}>{ fq.q }</h3>
          <span style={{fontSize: 18, color: '#4F46E5'}}>{ fq.symbol }</span>
        </div>
        {fq.open && (<React.Fragment>
          <p style={{padding: '0 24px 20px', fontSize: 14, color: '#475569', lineHeight: 1.6, margin: 0}}>{ fq.a }</p>
        </React.Fragment>)}
      </div>
    </React.Fragment>))}
  </div>
</section>

{/* FINAL CTA */}
<section style={{background: '#0F172A', padding: '96px 24px', textAlign: 'center'}}>
  <div style={{maxWidth: 700, margin: '0 auto'}}>
    <h2 className="disp" style={{fontSize: 38, fontWeight: 800, color: '#fff', margin: '0 0 16px', letterSpacing: '-0.01em'}}>Ready to automate your distribution business?</h2>
    <p style={{fontSize: 17, color: '#94A3B8', margin: '0 0 36px', lineHeight: 1.6}}>Join distributors across India who are replacing manual order chaos with a system that runs itself.</p>
    <div style={{display: 'flex', gap: 16, justifyContent: 'center', flexWrap: 'wrap', marginBottom: 16}}>
      <a href="https://calendly.com/consultme44/15min" target="_blank" rel="noopener noreferrer" style={{textDecoration: 'none'}}><button style={{background: 'transparent', border: '1px solid #475569', color: '#fff', fontWeight: 700, fontSize: 16, padding: '16px 28px', borderRadius: 12, cursor: 'pointer', fontFamily: '\'Inter\',sans-serif'}}>Book a Demo</button></a>
      <Link href="/auth" style={{textDecoration: 'none'}}><button style={{background: '#4F46E5', border: 'none', color: '#fff', fontWeight: 700, fontSize: 16, padding: '16px 28px', borderRadius: 12, cursor: 'pointer', boxShadow: '0 8px 24px rgba(79,70,229,0.4)', fontFamily: '\'Inter\',sans-serif'}}>Start Free Trial →</button></Link>
    </div>
    <p style={{fontSize: 13, color: '#64748B', margin: 0}}>No credit card required.</p>
  </div>
</section>

{/* FOOTER */}
<footer style={{background: '#fff', padding: '64px 24px 32px', borderTop: '1px solid #E2E8F0'}}>
  <div data-footer-grid="1" style={{maxWidth: 1200, margin: '0 auto', display: 'grid', gridTemplateColumns: '1.5fr 1fr 1fr 1fr', gap: 32, marginBottom: 48}}>
    <div className="disp" style={{fontSize: 20, fontWeight: 800, color: '#0F172A'}}>Distributor<span style={{color: '#4F46E5'}}>OS</span></div>
    <div>
      <h4 style={{fontSize: 13, fontWeight: 700, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.04em', margin: '0 0 16px'}}>Company</h4>
      <div style={{display: 'flex', flexDirection: 'column', gap: 12}}>
        <Link href="/privacy" style={{fontSize: 14, color: '#475569'}}>Privacy Policy</Link>
        <Link href="/terms" style={{fontSize: 14, color: '#475569'}}>Terms of Service</Link>
        <a href="mailto:contact@distroos.in" style={{fontSize: 14, color: '#475569'}}>Contact</a>
      </div>
    </div>
    <div>
      <h4 style={{fontSize: 13, fontWeight: 700, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.04em', margin: '0 0 16px'}}>Product</h4>
      <div style={{display: 'flex', flexDirection: 'column', gap: 12}}>
        <a href="#features" style={{fontSize: 14, color: '#475569'}}>Features</a>
        <a href="#pricing" style={{fontSize: 14, color: '#475569'}}>Pricing</a>
        <a href="#how-it-works" style={{fontSize: 14, color: '#475569'}}>How It Works</a>
      </div>
    </div>
    <div>
      <h4 style={{fontSize: 13, fontWeight: 700, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.04em', margin: '0 0 16px'}}>Connect</h4>
      <a href="mailto:contact@distroos.in" style={{fontSize: 14, color: '#475569'}}>contact@distroos.in</a>
    </div>
  </div>
  <div style={{maxWidth: 1200, margin: '0 auto', paddingTop: 24, borderTop: '1px solid #E2E8F0', textAlign: 'center'}}>
    <p style={{fontSize: 13, color: '#94A3B8', margin: 0}}>Made for Indian distributors 🇮🇳 · © 2026 DistributorOS</p>
  </div>
</footer>

</div>
  );
}
