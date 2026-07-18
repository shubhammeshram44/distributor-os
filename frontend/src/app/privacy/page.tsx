"use client";

import Link from "next/link";

export default function PrivacyPage() {
  return (
    <div className="max-w-3xl mx-auto px-6 py-16">
      <Link href="/" className="text-sm text-indigo-600 dark:text-indigo-400 hover:text-indigo-800 mb-8 inline-block">
        ← Back to Home
      </Link>
      <h1 className="text-3xl font-bold text-slate-900 dark:text-slate-50 mb-2">Privacy Policy</h1>
      <p className="text-slate-400 text-sm mb-10">Last updated: July 2026</p>

      <div className="prose prose-slate max-w-none">
        <h2 className="text-2xl font-bold text-slate-800 dark:text-slate-100 mt-8 mb-4">Who We Are</h2>
        <p className="text-slate-600 dark:text-slate-400 text-sm leading-relaxed mb-4">
          DistributorOS is a WhatsApp-based order management platform for Indian FMCG distributors. We are operated by Shubham Meshram, based in Bangalore, India.
        </p>
        <p className="text-slate-600 dark:text-slate-400 text-sm leading-relaxed mb-4">
          Contact: <a href="mailto:contact@distroos.in" className="text-indigo-600 dark:text-indigo-400 hover:underline">contact@distroos.in</a>
        </p>

        <hr className="my-8 border-slate-200 dark:border-white/10" />

        <h2 className="text-2xl font-bold text-slate-800 dark:text-slate-100 mt-8 mb-4">What Information We Collect</h2>
        
        <p className="font-semibold text-slate-700 dark:text-slate-300 text-sm mb-2">Information you give us:</p>
        <ul className="list-disc pl-5 text-slate-600 dark:text-slate-400 text-sm mb-4 space-y-1">
          <li>Your name, business name, and phone number when you sign up</li>
          <li>Your GSTIN and business address</li>
          <li>Products and customer details you add to the platform</li>
          <li>Orders placed through WhatsApp or the dashboard</li>
        </ul>

        <p className="font-semibold text-slate-700 dark:text-slate-300 text-sm mb-2">Information collected automatically:</p>
        <ul className="list-disc pl-5 text-slate-600 dark:text-slate-400 text-sm mb-4 space-y-1">
          <li>WhatsApp messages sent to your connected number (to process orders)</li>
          <li>Payment transaction data when using Razorpay integration</li>
          <li>Usage data (pages visited, features used) via Google Analytics and Microsoft Clarity</li>
        </ul>

        <hr className="my-8 border-slate-200 dark:border-white/10" />

        <h2 className="text-2xl font-bold text-slate-800 dark:text-slate-100 mt-8 mb-4">How We Use Your Information</h2>
        <p className="text-slate-600 dark:text-slate-400 text-sm leading-relaxed mb-4">
          We use your information to:
        </p>
        <ul className="list-disc pl-5 text-slate-600 dark:text-slate-400 text-sm mb-4 space-y-1">
          <li>Process WhatsApp orders using AI and create invoices</li>
          <li>Send payment links and reminders to your retailers</li>
          <li>Show you your business data on the dashboard</li>
          <li>Send you alerts about your account (e.g. WhatsApp disconnection)</li>
          <li>Improve the product</li>
        </ul>
        <p className="text-slate-600 dark:text-slate-400 text-sm leading-relaxed mb-4">
          We do <strong>not</strong> sell your data to anyone. We do <strong>not</strong> use your data for advertising.
        </p>

        <hr className="my-8 border-slate-200 dark:border-white/10" />

        <h2 className="text-2xl font-bold text-slate-800 dark:text-slate-100 mt-8 mb-4">Your Retailers' Data</h2>
        <p className="text-slate-600 dark:text-slate-400 text-sm leading-relaxed mb-4">
          When your retailers message you on WhatsApp, their phone numbers and order messages are processed by our system to create orders. This data is stored securely and used only to operate the platform for your business.
        </p>
        <p className="text-slate-600 dark:text-slate-400 text-sm leading-relaxed mb-4">
          You are responsible for informing your retailers that their orders are processed by DistributorOS.
        </p>

        <hr className="my-8 border-slate-200 dark:border-white/10" />

        <h2 className="text-2xl font-bold text-slate-800 dark:text-slate-100 mt-8 mb-4">Third-Party Services We Use</h2>
        <div className="overflow-x-auto my-6">
          <table className="w-full border-collapse border border-slate-200 dark:border-white/10 text-sm text-left">
            <thead>
              <tr className="bg-slate-50 dark:bg-dashboard-inset border-b border-slate-200 dark:border-white/10">
                <th className="border border-slate-200 dark:border-white/10 p-2.5 font-semibold text-slate-700 dark:text-slate-300">Service</th>
                <th className="border border-slate-200 dark:border-white/10 p-2.5 font-semibold text-slate-700 dark:text-slate-300">Purpose</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-slate-200 dark:border-white/10">
                <td className="border border-slate-200 dark:border-white/10 p-2.5 text-slate-600 dark:text-slate-400 font-medium">Google Firebase</td>
                <td className="border border-slate-200 dark:border-white/10 p-2.5 text-slate-600 dark:text-slate-400">Authentication (OTP login)</td>
              </tr>
              <tr className="border-b border-slate-200 dark:border-white/10">
                <td className="border border-slate-200 dark:border-white/10 p-2.5 text-slate-600 dark:text-slate-400 font-medium">Razorpay</td>
                <td className="border border-slate-200 dark:border-white/10 p-2.5 text-slate-600 dark:text-slate-400">Payment link generation</td>
              </tr>
              <tr className="border-b border-slate-200 dark:border-white/10">
                <td className="border border-slate-200 dark:border-white/10 p-2.5 text-slate-600 dark:text-slate-400 font-medium">Google Gemini AI</td>
                <td className="border border-slate-200 dark:border-white/10 p-2.5 text-slate-600 dark:text-slate-400">Order parsing from WhatsApp messages</td>
              </tr>
              <tr className="border-b border-slate-200 dark:border-white/10">
                <td className="border border-slate-200 dark:border-white/10 p-2.5 text-slate-600 dark:text-slate-400 font-medium">Evolution API</td>
                <td className="border border-slate-200 dark:border-white/10 p-2.5 text-slate-600 dark:text-slate-400">WhatsApp connectivity</td>
              </tr>
              <tr className="border-b border-slate-200 dark:border-white/10">
                <td className="border border-slate-200 dark:border-white/10 p-2.5 text-slate-600 dark:text-slate-400 font-medium">Google Analytics</td>
                <td className="border border-slate-200 dark:border-white/10 p-2.5 text-slate-600 dark:text-slate-400">Usage analytics</td>
              </tr>
              <tr className="border-b border-slate-200 dark:border-white/10">
                <td className="border border-slate-200 dark:border-white/10 p-2.5 text-slate-600 dark:text-slate-400 font-medium">Microsoft Clarity</td>
                <td className="border border-slate-200 dark:border-white/10 p-2.5 text-slate-600 dark:text-slate-400">User behaviour analytics</td>
              </tr>
              <tr className="border-b border-slate-200 dark:border-white/10">
                <td className="border border-slate-200 dark:border-white/10 p-2.5 text-slate-600 dark:text-slate-400 font-medium">Neon (PostgreSQL)</td>
                <td className="border border-slate-200 dark:border-white/10 p-2.5 text-slate-600 dark:text-slate-400">Data storage</td>
              </tr>
              <tr className="border-b border-slate-200 dark:border-white/10">
                <td className="border border-slate-200 dark:border-white/10 p-2.5 text-slate-600 dark:text-slate-400 font-medium">Render</td>
                <td className="border border-slate-200 dark:border-white/10 p-2.5 text-slate-600 dark:text-slate-400">Cloud hosting</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="text-slate-500 dark:text-slate-400 text-xs italic mb-4">
          Each of these services has their own privacy policy. We share only the minimum data needed for each service to function.
        </p>

        <hr className="my-8 border-slate-200 dark:border-white/10" />

        <h2 className="text-2xl font-bold text-slate-800 dark:text-slate-100 mt-8 mb-4">Data Storage and Security</h2>
        <ul className="list-disc pl-5 text-slate-600 dark:text-slate-400 text-sm mb-4 space-y-1">
          <li>Your data is stored on secure cloud servers (Render + Neon)</li>
          <li>Razorpay API keys are encrypted using AES-256 before storage</li>
          <li>We use HTTPS for all data transmission</li>
          <li>We do not store WhatsApp session data beyond what is needed to operate the connection</li>
        </ul>

        <hr className="my-8 border-slate-200 dark:border-white/10" />

        <h2 className="text-2xl font-bold text-slate-800 dark:text-slate-100 mt-8 mb-4">Data Retention</h2>
        <ul className="list-disc pl-5 text-slate-600 dark:text-slate-400 text-sm mb-4 space-y-1">
          <li>Your account data is retained as long as your account is active</li>
          <li>If you delete your account, we delete your data within 30 days</li>
          <li>Order history may be retained for up to 90 days after deletion for legal compliance</li>
        </ul>

        <hr className="my-8 border-slate-200 dark:border-white/10" />

        <h2 className="text-2xl font-bold text-slate-800 dark:text-slate-100 mt-8 mb-4">Your Rights</h2>
        <p className="text-slate-600 dark:text-slate-400 text-sm leading-relaxed mb-4">
          You have the right to:
        </p>
        <ul className="list-disc pl-5 text-slate-600 dark:text-slate-400 text-sm mb-4 space-y-1">
          <li>Access the data we hold about you</li>
          <li>Correct inaccurate data</li>
          <li>Delete your account and data</li>
          <li>Export your order and customer data</li>
        </ul>
        <p className="text-slate-600 dark:text-slate-400 text-sm leading-relaxed mb-4">
          To exercise any of these rights, email us at <a href="mailto:contact@distroos.in" className="text-indigo-600 dark:text-indigo-400 hover:underline">contact@distroos.in</a>
        </p>

        <hr className="my-8 border-slate-200 dark:border-white/10" />

        <h2 className="text-2xl font-bold text-slate-800 dark:text-slate-100 mt-8 mb-4">Cookies</h2>
        <p className="text-slate-600 dark:text-slate-400 text-sm leading-relaxed mb-4">
          We use cookies for:
        </p>
        <ul className="list-disc pl-5 text-slate-600 dark:text-slate-400 text-sm mb-4 space-y-1">
          <li>Keeping you logged in</li>
          <li>Analytics (Google Analytics, Microsoft Clarity)</li>
        </ul>
        <p className="text-slate-600 dark:text-slate-400 text-sm leading-relaxed mb-4">
          You can disable cookies in your browser settings. This may affect some features.
        </p>

        <hr className="my-8 border-slate-200 dark:border-white/10" />

        <h2 className="text-2xl font-bold text-slate-800 dark:text-slate-100 mt-8 mb-4">Changes to This Policy</h2>
        <p className="text-slate-600 dark:text-slate-400 text-sm leading-relaxed mb-4">
          We may update this policy occasionally. We will notify you by email or dashboard notification if we make significant changes.
        </p>

        <hr className="my-8 border-slate-200 dark:border-white/10" />

        <h2 className="text-2xl font-bold text-slate-800 dark:text-slate-100 mt-8 mb-4">Contact Us</h2>
        <p className="text-slate-600 dark:text-slate-400 text-sm leading-relaxed mb-4">
          For any privacy-related questions:
        </p>
        <p className="text-slate-600 dark:text-slate-400 text-sm leading-relaxed mb-1">
          <strong>Email:</strong> <a href="mailto:contact@distroos.in" className="text-indigo-600 dark:text-indigo-400 hover:underline">contact@distroos.in</a>
        </p>
        <p className="text-slate-600 dark:text-slate-400 text-sm leading-relaxed mb-4">
          <strong>Response time:</strong> Within 2 business days
        </p>
      </div>
    </div>
  );
}
