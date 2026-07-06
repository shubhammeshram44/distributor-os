"use client";

import React, { useState, useEffect, useRef, useMemo } from "react";
import Link from "next/link";
import { Figtree } from 'next/font/google';

const figtree = Figtree({ subsets: ['latin'] });

export default function MarketingPage() {
  const [isMobile, setIsMobile] = useState(false);
  const [navOpen, setNavOpen] = useState(false);
  const [visible, setVisible] = useState<Record<string, boolean>>({});
  const [faqOpenIdx, setFaqOpenIdx] = useState<number | null>(null);
  const [demoTyped, setDemoTyped] = useState('');
  const [demoShowOrder, setDemoShowOrder] = useState(false);
  const [statDistributors, setStatDistributors] = useState(0);
  const [statCrores, setStatCrores] = useState(0);

  const demoMessage = 'bhaiya 50 units rin soap bhejo 🙏';

  // Refs for scroll observation
  const refProblem = useRef<HTMLDivElement>(null);
  const refHow = useRef<HTMLDivElement>(null);
  const refFeatures = useRef<HTMLDivElement>(null);
  const refProof = useRef<HTMLDivElement>(null);
  const refPricing = useRef<HTMLDivElement>(null);
  const refFaq = useRef<HTMLDivElement>(null);

  // Resize listener
  useEffect(() => {
    const onResize = () => {
      setIsMobile(window.innerWidth < 860);
    };
    onResize();
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  // Demo loop
  useEffect(() => {
    let mounted = true;
    const sleep = (ms: number) => new Promise(res => setTimeout(res, ms));
    const runDemoLoop = async () => {
      while (mounted) {
        setDemoTyped('');
        setDemoShowOrder(false);
        await sleep(500);
        for (let i = 1; i <= demoMessage.length; i++) {
          if (!mounted) return;
          setDemoTyped(demoMessage.slice(0, i));
          await sleep(55);
        }
        await sleep(600);
        if (!mounted) return;
        setDemoShowOrder(true);
        await sleep(3200);
      }
    };
    runDemoLoop();
    return () => {
      mounted = false;
    };
  }, []);

  // IntersectionObserver for animate-on-scroll
  useEffect(() => {
    const startCounters = () => {
      const duration = 1100;
      const start = performance.now();
      const step = (now: number) => {
        const t = Math.min(1, (now - start) / duration);
        const ease = 1 - Math.pow(1 - t, 3);
        setStatDistributors(Math.round(50 * ease));
        setStatCrores(Math.round(10 * ease));
        if (t < 1) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    };

    const observedKeys: Record<string, React.RefObject<HTMLDivElement>> = {
      problem: refProblem,
      how: refHow,
      features: refFeatures,
      proof: refProof,
      pricing: refPricing,
      faq: refFaq
    };

    const io = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          const key = entry.target.getAttribute('data-observe-key');
          if (key) {
            setVisible(prev => ({ ...prev, [key]: true }));
            if (key === 'proof') startCounters();
            io.unobserve(entry.target);
          }
        }
      });
    }, { threshold: 0.15 });

    Object.entries(observedKeys).forEach(([key, ref]) => {
      if (ref.current) {
        ref.current.setAttribute('data-observe-key', key);
        io.observe(ref.current);
      }
    });

    return () => io.disconnect();
  }, []);

  const toggleNav = () => setNavOpen(prev => !prev);

  const cardStyle = (visibleState: boolean, index: number) => {
    return {
      opacity: visibleState ? 1 : 0,
      transform: visibleState ? 'translateY(0)' : 'translateY(24px)',
      transition: `opacity 0.6s ease ${index * 0.08}s, transform 0.6s ease ${index * 0.08}s`,
    };
  };

  const problems = useMemo(() => {
    return [
      { icon: '💬', title: 'Orders lost in WhatsApp chats', desc: 'Retailer messages get buried in busy chat threads and missed entirely.' },
      { icon: '🧾', title: 'Manual billing wastes hours', desc: 'Creating invoices by hand, every single day, for every single order.' },
      { icon: '📞', title: 'Chasing payments is exhausting', desc: "Calling retailers again and again just to collect what you're owed." },
    ].map((p, i) => ({ ...p, style: { background: '#f8fafc', border: '1px solid #eef2f7', borderRadius: '16px', padding: '32px 26px', ...cardStyle(visible.problem, i) } as React.CSSProperties }));
  }, [visible.problem]);

  const steps = useMemo(() => {
    return [
      { num: '1', title: 'Retailer sends a WhatsApp message', desc: '"bhaiya 50 units rin soap bhejo" — our AI reads it instantly, in Hindi, English or both.' },
      { num: '2', title: 'Order is created automatically', desc: 'Invoice generated, inventory updated — no typing, no spreadsheets.' },
      { num: '3', title: 'Payment link sent, auto-reconciled', desc: 'Retailer pays on WhatsApp. Payment is matched to the order the moment it lands.' },
    ].map((s, i) => ({ ...s, style: { position: 'relative', padding: '30px 26px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '16px', ...cardStyle(visible.how, i) } as React.CSSProperties }));
  }, [visible.how]);

  const features = useMemo(() => {
    return [
      { icon: '🤖', title: 'WhatsApp AI Order Parsing', desc: 'Hindi, English, mixed — all understood, instantly.' },
      { icon: '🧾', title: 'Auto Invoice Generation', desc: 'GST bill or retail bill, ready in one click.' },
      { icon: '📦', title: 'Smart Inventory Tracking', desc: "Know exactly what's in stock before you confirm an order." },
      { icon: '💳', title: 'Payment Collection', desc: 'Razorpay links sent automatically, every payment tracked.' },
      { icon: '🚚', title: 'Delivery Management', desc: 'Assign to a driver, track dispatch, notify the retailer.' },
      { icon: '⏰', title: 'Payment Reminders', desc: 'Automatic WhatsApp reminders for overdue payments.' },
    ].map((f, i) => ({ ...f, style: { display: 'flex', gap: '18px', padding: '24px', borderRadius: '14px', border: '1px solid #eef2f7', ...cardStyle(visible.features, i) } as React.CSSProperties }));
  }, [visible.features]);

  const testimonials = useMemo(() => {
    return [
      { name: 'Rajesh Gupta', city: 'Kanpur, UP', initial: 'R', quote: 'Ab main WhatsApp pe order aate hi dekh leta hoon — billing khud ho jaati hai.' },
      { name: 'Sunil Deshmukh', city: 'Nashik, MH', initial: 'S', quote: 'Payment ke liye phone karna band ho gaya. Reminder khud chala jaata hai.' },
      { name: 'Anita Reddy', city: 'Vijayawada, AP', initial: 'A', quote: 'Stock ka pata hamesha rehta hai. Galti se order confirm nahi hota.' },
    ].map((t, i) => ({ ...t, style: { background: '#ffffff', border: '1px solid #eef2f7', borderRadius: '16px', padding: '28px', ...cardStyle(visible.proof, i) } as React.CSSProperties }));
  }, [visible.proof]);

  const pricingPlans = useMemo(() => {
    return [
      { name: 'Free Trial', price: '₹0', period: '/15 days', highlight: false,
        features: ['All features included', 'No credit card needed', 'Full WhatsApp AI parsing', 'Cancel anytime'],
        cta: 'Start Free Trial', bg: '#f8fafc', textColor: '#0f172a', subColor: '#64748b', btnBg: '#0f172a', btnColor: '#ffffff', border: '1px solid #eef2f7' },
      { name: 'Growth', price: '₹2,999', period: '/month', highlight: true,
        features: ['Up to 300 orders/month', '1 WhatsApp number', 'Auto invoicing & payments', 'Email support'],
        cta: 'Choose Growth', bg: '#0f172a', textColor: '#ffffff', subColor: '#94a3b8', btnBg: '#10b981', btnColor: '#ffffff', border: '1px solid #0f172a' },
      { name: 'Scale', price: '₹5,999', period: '/month', highlight: false,
        features: ['Unlimited orders', '3 WhatsApp numbers', 'Priority support', 'Dedicated onboarding'],
        cta: 'Choose Scale', bg: '#f8fafc', textColor: '#0f172a', subColor: '#64748b', btnBg: '#0f172a', btnColor: '#ffffff', border: '1px solid #eef2f7' },
    ].map((p, i) => ({
      ...p,
      style: {
        display: 'flex', flexDirection: 'column', background: p.bg, border: p.border, borderRadius: '18px',
        padding: '32px 28px', transform: p.highlight ? 'scale(1.03)' : 'scale(1)',
        boxShadow: p.highlight ? '0 24px 50px rgba(15,23,42,0.25)' : '0 1px 2px rgba(0,0,0,0.02)',
        transition: 'transform 0.25s ease, box-shadow 0.25s ease',
      } as React.CSSProperties,
    }));
  }, []);

  const faqData = [
    { q: 'Do my retailers need to download an app?', a: 'No. They just WhatsApp you as usual — nothing changes for them.' },
    { q: 'What languages does it understand?', a: 'Hindi, English, and mixed Hinglish — however your retailers naturally type.' },
    { q: 'Do I need to change how I work?', a: 'No. You keep using WhatsApp exactly as before. We automate everything behind it.' },
    { q: 'What happens if the AI misreads an order?', a: 'You review and confirm every order before anything is dispatched.' },
    { q: 'Is my data safe?', a: 'Yes. Hosted on secure cloud servers with daily backups.' },
  ];

  const faqs = useMemo(() => {
    return faqData.map((f, i) => ({
      ...f,
      open: faqOpenIdx === i,
      symbol: faqOpenIdx === i ? '−' : '+',
      toggle: () => setFaqOpenIdx(prev => prev === i ? null : i),
    }));
  }, [faqOpenIdx]);

  const navToggleIcon = navOpen ? '✕' : '☰';
  const demoShowOrderNot = !demoShowOrder;
  const isMobileNav = isMobile;
  const isMobileNotNav = !isMobile;
  const demoOrderStyle = {
    background: '#ffffff', borderRadius: '16px', padding: '20px', boxShadow: '0 20px 45px rgba(0,0,0,0.35)',
    animation: 'heroBubbleIn 0.5s ease',
  } as React.CSSProperties;

  return (

<div className={figtree.className} style={{fontFamily: '\'Figtree\', \'Inter\', -apple-system, sans-serif', color: '#0f172a', background: '#ffffff', width: '100%', overflowX: 'hidden', minHeight: '100vh'}}>

  {/* NAV */}
  <div style={{position: 'sticky', top: 0, zIndex: 100, background: 'rgba(15,23,42,0.97)', backdropFilter: 'blur(8px)', borderBottom: '1px solid rgba(255,255,255,0.08)'}}>
    <div style={{maxWidth: 1200, margin: '0 auto', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 24px'}}>
      <div style={{display: 'flex', alignItems: 'center', gap: 10}}>
        <div style={{width: 34, height: 34, borderRadius: 9, background: 'linear-gradient(135deg, #10b981, #0ea371)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18, flexShrink: 0}}>💬</div>
        <div style={{fontWeight: 800, fontSize: 18, color: '#ffffff', letterSpacing: '-0.02em'}}>Distributor<span style={{color: '#10b981'}}>OS</span></div>
      </div>
      {isMobileNav && (<React.Fragment>
        <div style={{display: 'flex', alignItems: 'center', gap: 10}}>
          <Link href="/auth" style={{background: '#10b981', color: '#ffffff', fontWeight: 700, fontSize: 13, padding: '9px 14px', borderRadius: 8, cursor: 'pointer', whiteSpace: 'nowrap', textDecoration: 'none'}}>Start Trial</Link>
          <div onClick={toggleNav} style={{width: 38, height: 38, borderRadius: 8, background: 'rgba(255,255,255,0.08)', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', color: '#ffffff', fontSize: 18}}>{ navToggleIcon }</div>
        </div>
      </React.Fragment>)}
      {isMobileNotNav && (<React.Fragment>
        <div style={{display: 'flex', alignItems: 'center', gap: 32}}>
          <a href="#problem" style={{color: '#cbd5e1', textDecoration: 'none', fontSize: 14, fontWeight: 500}}>Problem</a>
          <a href="#how" style={{color: '#cbd5e1', textDecoration: 'none', fontSize: 14, fontWeight: 500}}>How it Works</a>
          <a href="#features" style={{color: '#cbd5e1', textDecoration: 'none', fontSize: 14, fontWeight: 500}}>Features</a>
          <a href="#pricing" style={{color: '#cbd5e1', textDecoration: 'none', fontSize: 14, fontWeight: 500}}>Pricing</a>
          <a href="#faq" style={{color: '#cbd5e1', textDecoration: 'none', fontSize: 14, fontWeight: 500}}>FAQ</a>
        </div>
        <Link href="/auth" style={{background: '#10b981', color: '#ffffff', fontWeight: 700, fontSize: 14, padding: '11px 20px', borderRadius: 8, cursor: 'pointer', whiteSpace: 'nowrap', textDecoration: 'none'}}>Start Free Trial</Link>
      </React.Fragment>)}
    </div>
    {navOpen && (<React.Fragment>
      <div style={{display: 'flex', flexDirection: 'column', gap: 4, padding: '8px 24px 18px'}}>
        <a href="#problem" style={{color: '#e2e8f0', textDecoration: 'none', fontSize: 15, fontWeight: 600, padding: '10px 0', borderBottom: '1px solid rgba(255,255,255,0.08)'}}>Problem</a>
        <a href="#how" style={{color: '#e2e8f0', textDecoration: 'none', fontSize: 15, fontWeight: 600, padding: '10px 0', borderBottom: '1px solid rgba(255,255,255,0.08)'}}>How it Works</a>
        <a href="#features" style={{color: '#e2e8f0', textDecoration: 'none', fontSize: 15, fontWeight: 600, padding: '10px 0', borderBottom: '1px solid rgba(255,255,255,0.08)'}}>Features</a>
        <a href="#pricing" style={{color: '#e2e8f0', textDecoration: 'none', fontSize: 15, fontWeight: 600, padding: '10px 0', borderBottom: '1px solid rgba(255,255,255,0.08)'}}>Pricing</a>
        <a href="#faq" style={{color: '#e2e8f0', textDecoration: 'none', fontSize: 15, fontWeight: 600, padding: '10px 0', borderBottom: '1px solid rgba(255,255,255,0.08)'}}>FAQ</a>
        <Link href="/auth" style={{color: '#e2e8f0', textDecoration: 'none', fontSize: 15, fontWeight: 600, padding: '10px 0', borderBottom: '1px solid rgba(255,255,255,0.08)'}}>
          Login
        </Link>
        <Link href="/auth" style={{color: '#10b981', textDecoration: 'none', fontSize: 15, fontWeight: 600, padding: '10px 0'}}>
          Get Started Free
        </Link>
      </div>
    </React.Fragment>)}
  </div>

  {/* HERO */}
  <div style={{background: 'linear-gradient(180deg, #0f172a 0%, #111c33 100%)', padding: 'clamp(48px,7vw,96px) 24px clamp(64px,9vw,110px)'}}>
    <div style={{maxWidth: 1200, margin: '0 auto', display: 'flex', flexWrap: 'wrap', gap: 56, alignItems: 'center'}}>
      <div style={{flex: '1 1 460px', minWidth: 300}}>
        <div style={{display: 'inline-flex', alignItems: 'center', gap: 8, background: 'rgba(16,185,129,0.12)', border: '1px solid rgba(16,185,129,0.3)', color: '#34d399', fontSize: 13, fontWeight: 600, padding: '7px 14px', borderRadius: 999, marginBottom: 22}}>
          <span>🟢</span> Built for Indian FMCG Distributors
        </div>
        <div style={{fontSize: 'clamp(34px, 5vw, 58px)', fontWeight: 900, color: '#ffffff', lineHeight: 1.08, letterSpacing: '-0.02em', marginBottom: 22}}>
          Turn WhatsApp Orders into a <span style={{color: '#10b981'}}>Business System</span> — Automatically
        </div>
        <div style={{fontSize: 'clamp(16px, 2vw, 19px)', color: '#94a3b8', lineHeight: 1.6, maxWidth: 560, marginBottom: 34}}>
          Your retailers message you on WhatsApp. DistributorOS reads it, creates the order, updates inventory, and sends them a payment link. You do nothing.
        </div>
        <div style={{display: 'flex', flexWrap: 'wrap', gap: 14}}>
          <Link href="/auth" style={{background: '#10b981', color: '#ffffff', fontWeight: 700, fontSize: 16, padding: '16px 28px', borderRadius: 10, cursor: 'pointer', boxShadow: '0 8px 24px rgba(16,185,129,0.35)', textDecoration: 'none'}}>Start Free Trial →</Link>
          <a href="#how" style={{textDecoration: 'none', border: '1.5px solid rgba(255,255,255,0.25)', color: '#ffffff', fontWeight: 700, fontSize: 16, padding: '16px 28px', borderRadius: 10, textAlign: 'center'}}>See How It Works</a>
        </div>
        <div style={{marginTop: 28, color: '#64748b', fontSize: 13}}>No credit card needed · 15-day free trial · Setup in 10 minutes</div>
      </div>

      <div style={{flex: '1 1 380px', minWidth: 300, display: 'flex', justifyContent: 'center', position: 'relative'}}>
        <div style={{animation: 'floatUpDown 4.5s ease-in-out infinite', position: 'relative', width: '100%', maxWidth: 400}}>
          {/* phone frame */}
          <div style={{background: '#1e293b', borderRadius: 30, padding: 12, boxShadow: '0 30px 70px rgba(0,0,0,0.45)', border: '1px solid rgba(255,255,255,0.06)'}}>
            <div style={{background: '#0b141a', borderRadius: 20, overflow: 'hidden'}}>
              <div style={{background: '#075e54', padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 10}}>
                <div style={{width: 30, height: 30, borderRadius: '50%', background: '#128c7e', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14}}>🏪</div>
                <div>
                  <div style={{color: '#ffffff', fontSize: 13, fontWeight: 700}}>Sharma General Store</div>
                  <div style={{color: '#cfe9e4', fontSize: 10}}>online</div>
                </div>
              </div>
              <div style={{background: '#0b141a', padding: 16, minHeight: 200, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', gap: 10}}>
                <div style={{alignSelf: 'flex-start', background: '#1f2c34', color: '#e9edef', fontSize: 13, padding: '9px 13px', borderRadius: '10px 10px 10px 2px', maxWidth: '82%', animation: 'heroBubbleIn 5.5s ease infinite'}}>
                  bhaiya 50 units rin soap bhejo 🙏
                </div>
                <div style={{alignSelf: 'flex-end', background: '#005c4b', color: '#e9edef', fontSize: 13, padding: '9px 13px', borderRadius: '10px 10px 2px 10px', maxWidth: '82%', animation: 'heroBubbleIn 5.5s ease infinite', animationDelay: '0.4s'}}>
                  ✅ Order confirmed! Pay here: rzp.io/i/os4
                </div>
              </div>
            </div>
          </div>
          {/* floating dashboard order card */}
          <div style={{position: 'absolute', right: -18, bottom: 30, width: 210, background: '#ffffff', borderRadius: 14, padding: 14, boxShadow: '0 20px 45px rgba(0,0,0,0.35)', animation: 'heroOrder 5.5s ease infinite'}}>
            <div style={{display: 'flex', alignItems: 'center', gap: 6, color: '#10b981', fontSize: 11, fontWeight: 700, marginBottom: 8}}>
              <span>●</span> NEW ORDER SYNCED
            </div>
            <div style={{fontSize: 13, fontWeight: 700, color: '#0f172a', marginBottom: 4}}>Rin Soap × 50 units</div>
            <div style={{fontSize: 12, color: '#64748b', marginBottom: 8}}>Sharma General Store</div>
            <div style={{display: 'flex', justifyContent: 'space-between', borderTop: '1px dashed #e2e8f0', paddingTop: 8}}>
              <span style={{fontSize: 11, color: '#94a3b8'}}>Amount</span>
              <span style={{fontSize: 13, fontWeight: 800, color: '#0f172a'}}>₹1,250</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  {/* PROBLEM */}
  <div id="problem" ref={ refProblem } style={{padding: 'clamp(56px,8vw,110px) 24px', background: '#ffffff'}}>
    <div style={{maxWidth: 1100, margin: '0 auto'}}>
      <div style={{textAlign: 'center', maxWidth: 640, margin: '0 auto 52px'}}>
        <div style={{color: '#10b981', fontWeight: 700, fontSize: 14, letterSpacing: '0.04em', textTransform: 'uppercase', marginBottom: 12}}>The Problem</div>
        <div style={{fontSize: 'clamp(26px,3.4vw,40px)', fontWeight: 800, color: '#0f172a', letterSpacing: '-0.02em'}}>Running orders on WhatsApp alone is chaos</div>
      </div>
      <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 24}}>
        {problems && problems.map((item, i) => (<React.Fragment key={i}>
          <div style={ item.style }>
            <div style={{width: 52, height: 52, borderRadius: 12, background: '#ffffff', border: '1px solid #eef2f7', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 24, marginBottom: 20}}>{ item.icon }</div>
            <div style={{fontSize: 19, fontWeight: 700, color: '#0f172a', marginBottom: 10}}>{ item.title }</div>
            <div style={{fontSize: 15, color: '#64748b', lineHeight: 1.55}}>{ item.desc }</div>
          </div>
        </React.Fragment>))}
      </div>
    </div>
  </div>

  {/* HOW IT WORKS */}
  <div id="how" ref={ refHow } style={{padding: 'clamp(56px,8vw,110px) 24px', background: '#0f172a'}}>
    <div style={{maxWidth: 1100, margin: '0 auto'}}>
      <div style={{textAlign: 'center', maxWidth: 640, margin: '0 auto 60px'}}>
        <div style={{color: '#34d399', fontWeight: 700, fontSize: 14, letterSpacing: '0.04em', textTransform: 'uppercase', marginBottom: 12}}>How It Works</div>
        <div style={{fontSize: 'clamp(26px,3.4vw,40px)', fontWeight: 800, color: '#ffffff', letterSpacing: '-0.02em'}}>From a WhatsApp message to a reconciled payment</div>
      </div>
      <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 32}}>
        {steps && steps.map((item, i) => (<React.Fragment key={i}>
          <div style={ item.style }>
            <div style={{fontSize: 46, fontWeight: 900, color: 'rgba(16,185,129,0.35)', lineHeight: 1, marginBottom: 18}}>{ item.num }</div>
            <div style={{fontSize: 18, fontWeight: 700, color: '#ffffff', marginBottom: 10}}>{ item.title }</div>
            <div style={{fontSize: 14.5, color: '#94a3b8', lineHeight: 1.6}}>{ item.desc }</div>
          </div>
        </React.Fragment>))}
      </div>
    </div>
  </div>

  {/* FEATURES */}
  <div id="features" ref={ refFeatures } style={{padding: 'clamp(56px,8vw,110px) 24px', background: '#ffffff'}}>
    <div style={{maxWidth: 1100, margin: '0 auto'}}>
      <div style={{textAlign: 'center', maxWidth: 640, margin: '0 auto 52px'}}>
        <div style={{color: '#10b981', fontWeight: 700, fontSize: 14, letterSpacing: '0.04em', textTransform: 'uppercase', marginBottom: 12}}>Features</div>
        <div style={{fontSize: 'clamp(26px,3.4vw,40px)', fontWeight: 800, color: '#0f172a', letterSpacing: '-0.02em'}}>Everything your business runs on, automated</div>
      </div>
      <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 20}}>
        {features && features.map((item, i) => (<React.Fragment key={i}>
          <div style={ item.style }>
            <div style={{width: 48, height: 48, borderRadius: 12, background: '#ecfdf5', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 22, flexShrink: 0}}>{ item.icon }</div>
            <div>
              <div style={{fontSize: 17, fontWeight: 700, color: '#0f172a', marginBottom: 6}}>{ item.title }</div>
              <div style={{fontSize: 14.5, color: '#64748b', lineHeight: 1.55}}>{ item.desc }</div>
            </div>
          </div>
        </React.Fragment>))}
      </div>
    </div>
  </div>

  {/* SOCIAL PROOF */}
  <div id="proof" ref={ refProof } style={{padding: 'clamp(56px,8vw,100px) 24px', background: '#f8fafc'}}>
    <div style={{maxWidth: 1100, margin: '0 auto'}}>
      <div style={{textAlign: 'center', marginBottom: 52}}>
        <div style={{fontSize: 'clamp(24px,3.2vw,36px)', fontWeight: 800, color: '#0f172a', letterSpacing: '-0.02em'}}>
          Join <span style={{color: '#10b981'}}>{ statDistributors }+</span> distributors managing <span style={{color: '#10b981'}}>₹{ statCrores } Cr+</span> in monthly orders
        </div>
      </div>
      <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 22}}>
        {testimonials && testimonials.map((item, i) => (<React.Fragment key={i}>
          <div style={ item.style }>
            <div style={{color: '#f59e0b', fontSize: 14, marginBottom: 14}}>★★★★★</div>
            <div style={{fontSize: 15, color: '#334155', lineHeight: 1.6, marginBottom: 20}}>"{ item.quote }"</div>
            <div style={{display: 'flex', alignItems: 'center', gap: 12}}>
              <div style={{width: 40, height: 40, borderRadius: '50%', background: '#0f172a', color: '#ffffff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: 15}}>{ item.initial }</div>
              <div>
                <div style={{fontSize: 14, fontWeight: 700, color: '#0f172a'}}>{ item.name }</div>
                <div style={{fontSize: 13, color: '#94a3b8'}}>{ item.city }</div>
              </div>
            </div>
          </div>
        </React.Fragment>))}
      </div>
    </div>
  </div>

  {/* LIVE DEMO */}
  <div style={{padding: 'clamp(56px,8vw,110px) 24px', background: '#0f172a'}}>
    <div style={{maxWidth: 900, margin: '0 auto'}}>
      <div style={{textAlign: 'center', maxWidth: 640, margin: '0 auto 48px'}}>
        <div style={{color: '#34d399', fontWeight: 700, fontSize: 14, letterSpacing: '0.04em', textTransform: 'uppercase', marginBottom: 12}}>See It In Action</div>
        <div style={{fontSize: 'clamp(26px,3.4vw,38px)', fontWeight: 800, color: '#ffffff', letterSpacing: '-0.02em'}}>Watch a real order happen, live</div>
      </div>
      <div style={{display: 'flex', flexWrap: 'wrap', gap: 28, alignItems: 'center', justifyContent: 'center'}}>
        <div style={{flex: '1 1 320px', maxWidth: 380, background: '#0b141a', borderRadius: 18, padding: 20, border: '1px solid rgba(255,255,255,0.08)'}}>
          <div style={{display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16}}>
            <div style={{width: 28, height: 28, borderRadius: '50%', background: '#25D366', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13}}>💬</div>
            <div style={{color: '#cbd5e1', fontSize: 13, fontWeight: 600}}>WhatsApp — Retailer</div>
          </div>
          <div style={{background: '#1f2c34', borderRadius: '10px 10px 10px 2px', padding: '14px 16px', minHeight: 46, color: '#e9edef', fontSize: 15}}>
            { demoTyped }<span style={{animation: 'blinkCursor 1s step-start infinite'}}>|</span>
          </div>
        </div>
        <div style={{fontSize: 26, color: '#475569'}}>→</div>
        <div style={{flex: '1 1 300px', maxWidth: 320}}>
          {demoShowOrder && (<React.Fragment>
            <div style={ demoOrderStyle }>
              <div style={{display: 'flex', alignItems: 'center', gap: 6, color: '#10b981', fontSize: 11, fontWeight: 700, marginBottom: 10}}>
                <span>●</span> ORDER CREATED
              </div>
              <div style={{fontSize: 15, fontWeight: 700, color: '#0f172a', marginBottom: 4}}>Rin Soap × 50 units</div>
              <div style={{fontSize: 13, color: '#64748b', marginBottom: 10}}>Sharma General Store · Kanpur</div>
              <div style={{display: 'flex', justifyContent: 'space-between', borderTop: '1px dashed #e2e8f0', paddingTop: 10, marginBottom: 8}}>
                <span style={{fontSize: 12, color: '#94a3b8'}}>Amount</span>
                <span style={{fontSize: 14, fontWeight: 800, color: '#0f172a'}}>₹1,250</span>
              </div>
              <div style={{background: '#ecfdf5', color: '#059669', fontSize: 12, fontWeight: 700, padding: '8px 10px', borderRadius: 8, textAlign: 'center'}}>Payment link sent via WhatsApp ✓</div>
            </div>
          </React.Fragment>)}
          {demoShowOrderNot && (<React.Fragment>
            <div style={{border: '1.5px dashed rgba(255,255,255,0.15)', borderRadius: 16, padding: '40px 20px', textAlign: 'center', color: '#475569', fontSize: 13}}>Order will appear here</div>
          </React.Fragment>)}
        </div>
      </div>
    </div>
  </div>

  {/* PRICING */}
  <div id="pricing" ref={ refPricing } style={{padding: 'clamp(56px,8vw,110px) 24px', background: '#ffffff'}}>
    <div style={{maxWidth: 1100, margin: '0 auto'}}>
      <div style={{textAlign: 'center', maxWidth: 640, margin: '0 auto 52px'}}>
        <div style={{color: '#10b981', fontWeight: 700, fontSize: 14, letterSpacing: '0.04em', textTransform: 'uppercase', marginBottom: 12}}>Pricing</div>
        <div style={{fontSize: 'clamp(26px,3.4vw,40px)', fontWeight: 800, color: '#0f172a', letterSpacing: '-0.02em'}}>Simple pricing, no surprises</div>
      </div>
      <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 24, alignItems: 'stretch'}}>
        {pricingPlans && pricingPlans.map((item, i) => (<React.Fragment key={i}>
          <div style={ item.style }>
            {item.highlight && (<React.Fragment>
              <div style={{background: '#10b981', color: '#ffffff', fontSize: 12, fontWeight: 700, padding: '5px 14px', borderRadius: 999, display: 'inline-block', marginBottom: 16, alignSelf: 'flex-start'}}>MOST POPULAR</div>
            </React.Fragment>)}
            <div style={{fontSize: 18, fontWeight: 700, color: item.textColor, marginBottom: 6}}>{ item.name }</div>
            <div style={{display: 'flex', alignItems: 'baseline', gap: 4, marginBottom: 24}}>
              <span style={{fontSize: 36, fontWeight: 900, color: item.textColor}}>{ item.price }</span>
              <span style={{fontSize: 14, color: item.subColor}}>{ item.period }</span>
            </div>
            <div style={{display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 28, flex: 1}}>
              {item.features && item.features.map((f, i) => (<React.Fragment key={i}>
                <div style={{display: 'flex', alignItems: 'flex-start', gap: 8, fontSize: 14, color: item.subColor}}>
                  <span style={{color: '#10b981', fontWeight: 700}}>✓</span> { f }
                </div>
              </React.Fragment>))}
            </div>
            <Link href="/auth" style={{background: item.btnBg, color: item.btnColor, fontWeight: 700, fontSize: 15, padding: 14, borderRadius: 10, cursor: 'pointer', textAlign: 'center', textDecoration: 'none', display: 'block'}}>{ item.cta }</Link>
          </div>
        </React.Fragment>))}
      </div>
    </div>
  </div>

  {/* FAQ */}
  <div id="faq" ref={ refFaq } style={{padding: 'clamp(56px,8vw,110px) 24px', background: '#f8fafc'}}>
    <div style={{maxWidth: 760, margin: '0 auto'}}>
      <div style={{textAlign: 'center', marginBottom: 44}}>
        <div style={{color: '#10b981', fontWeight: 700, fontSize: 14, letterSpacing: '0.04em', textTransform: 'uppercase', marginBottom: 12}}>FAQ</div>
        <div style={{fontSize: 'clamp(26px,3.4vw,36px)', fontWeight: 800, color: '#0f172a', letterSpacing: '-0.02em'}}>Common questions</div>
      </div>
      <div style={{display: 'flex', flexDirection: 'column', gap: 12}}>
        {faqs && faqs.map((item, i) => (<React.Fragment key={i}>
          <div style={{background: '#ffffff', border: '1px solid #eef2f7', borderRadius: 14, overflow: 'hidden'}}>
            <div onClick={item.toggle} style={{display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '20px 22px', cursor: 'pointer'}}>
              <div style={{fontSize: 15.5, fontWeight: 700, color: '#0f172a'}}>{ item.q }</div>
              <div style={{fontSize: 20, color: '#10b981', fontWeight: 300, flexShrink: 0, marginLeft: 12}}>{ item.symbol }</div>
            </div>
            {item.open && (<React.Fragment>
              <div style={{padding: '0 22px 20px', fontSize: 14.5, color: '#64748b', lineHeight: 1.6}}>{ item.a }</div>
            </React.Fragment>)}
          </div>
        </React.Fragment>))}
      </div>
    </div>
  </div>

  {/* FOOTER */}
  <div style={{background: '#0f172a', padding: '56px 24px 32px'}}>
    <div style={{maxWidth: 1100, margin: '0 auto'}}>
      <div style={{display: 'flex', flexWrap: 'wrap', gap: 40, justifyContent: 'space-between', paddingBottom: 32, borderBottom: '1px solid rgba(255,255,255,0.08)'}}>
        <div style={{flex: '1 1 260px', maxWidth: 340}}>
          <div style={{display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14}}>
            <div style={{width: 32, height: 32, borderRadius: 8, background: 'linear-gradient(135deg, #10b981, #0ea371)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16}}>💬</div>
            <div style={{fontWeight: 800, fontSize: 17, color: '#ffffff'}}>Distributor<span style={{color: '#10b981'}}>OS</span></div>
          </div>
          <div style={{color: '#64748b', fontSize: 14, lineHeight: 1.6}}>Your distributor's WhatsApp is now a full business.</div>
        </div>
        <div style={{display: 'flex', gap: 60, flexWrap: 'wrap'}}>
          <div>
            <div style={{color: '#ffffff', fontSize: 13, fontWeight: 700, marginBottom: 14}}>Company</div>
            <div style={{display: 'flex', flexDirection: 'column', gap: 10}}>
              <a href="#" style={{color: '#94a3b8', textDecoration: 'none', fontSize: 14}}>Privacy</a>
              <a href="#" style={{color: '#94a3b8', textDecoration: 'none', fontSize: 14}}>Terms</a>
              <Link href="/auth" style={{color: '#94a3b8', fontSize: 14, cursor: 'pointer', textDecoration: 'none'}}>Contact</Link>
            </div>
          </div>
        </div>
      </div>
      <div style={{paddingTop: 24, textAlign: 'center', color: '#475569', fontSize: 13}}>Made for Indian distributors 🇮🇳 · © 2026 DistributorOS</div>
    </div>
  </div>



</div>
  );
}
