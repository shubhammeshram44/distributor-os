"use client";

import Link from "next/link";

export default function TermsPage() {
  return (
    <div className="max-w-3xl mx-auto px-6 py-16">
      <Link href="/" className="text-sm text-indigo-600 hover:text-indigo-800 mb-8 inline-block">
        ← Back to Home
      </Link>
      <h1 className="text-3xl font-bold text-slate-900 mb-2">Terms of Service</h1>
      <p className="text-slate-400 text-sm mb-10">Last updated: July 2026</p>

      <div className="prose prose-slate max-w-none">
        <h2 className="text-2xl font-bold text-slate-800 mt-8 mb-4">Agreement</h2>
        <p className="text-slate-600 text-sm leading-relaxed mb-4">
          By signing up for DistributorOS, you agree to these terms. Please read them carefully.
        </p>
        <p className="text-slate-600 text-sm leading-relaxed mb-4">
          If you do not agree, please do not use the platform.
        </p>

        <hr className="my-8 border-slate-200" />

        <h2 className="text-2xl font-bold text-slate-800 mt-8 mb-4">What DistributorOS Does</h2>
        <p className="text-slate-600 text-sm leading-relaxed mb-4">
          DistributorOS is a software platform that helps FMCG distributors:
        </p>
        <ul className="list-disc pl-5 text-slate-600 text-sm mb-4 space-y-1">
          <li>Receive and process orders from retailers via WhatsApp</li>
          <li>Generate GST and retail invoices</li>
          <li>Track inventory and payments</li>
          <li>Send payment links and reminders</li>
        </ul>
        <p className="text-slate-600 text-sm leading-relaxed mb-4">
          We are a software tool. We are not a distributor, payment processor, or financial institution.
        </p>

        <hr className="my-8 border-slate-200" />

        <h2 className="text-2xl font-bold text-slate-800 mt-8 mb-4">Your Account</h2>
        <p className="font-semibold text-slate-700 text-sm mb-2">You are responsible for:</p>
        <ul className="list-disc pl-5 text-slate-600 text-sm mb-4 space-y-1">
          <li>Keeping your login credentials secure</li>
          <li>All activity that happens under your account</li>
          <li>The accuracy of your business information (GSTIN, business name, etc.)</li>
          <li>Informing your retailers that their orders are processed by our platform</li>
        </ul>

        <p className="font-semibold text-slate-700 text-sm mb-2">You must not:</p>
        <ul className="list-disc pl-5 text-slate-600 text-sm mb-4 space-y-1">
          <li>Share your account with other businesses</li>
          <li>Use the platform for any illegal purpose</li>
          <li>Attempt to reverse-engineer or copy the software</li>
          <li>Use automated scripts to abuse the platform</li>
        </ul>

        <hr className="my-8 border-slate-200" />

        <h2 className="text-2xl font-bold text-slate-800 mt-8 mb-4">WhatsApp Usage</h2>
        <p className="text-slate-600 text-sm leading-relaxed mb-4">
          You are responsible for ensuring your use of WhatsApp through our platform complies with WhatsApp's Terms of Service. DistributorOS connects to WhatsApp via a third-party API. WhatsApp may change their policies at any time which could affect the service.
        </p>
        <p className="text-slate-600 text-sm leading-relaxed mb-4">
          We cannot guarantee uninterrupted WhatsApp connectivity as it depends on third-party services outside our control.
        </p>

        <hr className="my-8 border-slate-200" />

        <h2 className="text-2xl font-bold text-slate-800 mt-8 mb-4">Payments</h2>
        <p className="font-semibold text-slate-700 text-sm mb-2">Subscription fees:</p>
        <ul className="list-disc pl-5 text-slate-600 text-sm mb-4 space-y-1">
          <li>Billed monthly in advance</li>
          <li>No refunds for partial months</li>
          <li>We will notify you 7 days before any price changes</li>
        </ul>

        <p className="font-semibold text-slate-700 text-sm mb-2">Razorpay integration:</p>
        <ul className="list-disc pl-5 text-slate-600 text-sm mb-4 space-y-1">
          <li>When you connect your Razorpay account, payments from your retailers go directly to your bank account</li>
          <li>DistributorOS does not handle or hold your money</li>
          <li>Razorpay's own terms apply to all payment transactions</li>
        </ul>

        <hr className="my-8 border-slate-200" />

        <h2 className="text-2xl font-bold text-slate-800 mt-8 mb-4">Data and Privacy</h2>
        <p className="text-slate-600 text-sm leading-relaxed mb-4">
          Your data belongs to you. We store it securely to operate the platform. See our <Link href="/privacy" className="text-indigo-600 hover:underline">Privacy Policy</Link> for full details.
        </p>
        <p className="text-slate-600 text-sm leading-relaxed mb-4">
          You can export or delete your data at any time by contacting us at <a href="mailto:contact@distroos.in" className="text-indigo-600 hover:underline">contact@distroos.in</a>.
        </p>

        <hr className="my-8 border-slate-200" />

        <h2 className="text-2xl font-bold text-slate-800 mt-8 mb-4">Uptime and Reliability</h2>
        <p className="text-slate-600 text-sm leading-relaxed mb-4">
          We aim for high availability but cannot guarantee 100% uptime. The platform depends on several third-party services (WhatsApp, Razorpay, Google AI) which may have their own outages.
        </p>
        <p className="font-semibold text-slate-700 text-sm mb-2">We are not liable for:</p>
        <ul className="list-disc pl-5 text-slate-600 text-sm mb-4 space-y-1">
          <li>Lost orders due to WhatsApp disconnection</li>
          <li>Payment failures due to Razorpay issues</li>
          <li>AI parsing errors that result in incorrect orders</li>
        </ul>
        <p className="text-slate-600 text-sm leading-relaxed mb-4">
          You should always verify critical orders before dispatching goods.
        </p>

        <hr className="my-8 border-slate-200" />

        <h2 className="text-2xl font-bold text-slate-800 mt-8 mb-4">Limitation of Liability</h2>
        <p className="text-slate-600 text-sm leading-relaxed mb-4">
          DistributorOS is provided "as is." We are not liable for:
        </p>
        <ul className="list-disc pl-5 text-slate-600 text-sm mb-4 space-y-1">
          <li>Any business losses resulting from use of the platform</li>
          <li>Incorrect order parsing by AI</li>
          <li>Data loss (though we take all reasonable precautions)</li>
          <li>Third-party service failures</li>
        </ul>
        <p className="text-slate-600 text-sm leading-relaxed mb-4">
          Our total liability to you shall not exceed the amount you paid us in the 3 months prior to the claim.
        </p>

        <hr className="my-8 border-slate-200" />

        <h2 className="text-2xl font-bold text-slate-800 mt-8 mb-4">Termination</h2>
        <p className="text-slate-600 text-sm leading-relaxed mb-4">
          <strong>You can cancel anytime</strong> by emailing <a href="mailto:contact@distroos.in" className="text-indigo-600 hover:underline">contact@distroos.in</a>. Your account will remain active until the end of your billing period.
        </p>
        <p className="font-semibold text-slate-700 text-sm mb-2">We may suspend or terminate your account if:</p>
        <ul className="list-disc pl-5 text-slate-600 text-sm mb-4 space-y-1">
          <li>You violate these terms</li>
          <li>Your account is used for illegal activity</li>
          <li>You abuse the platform or other users</li>
        </ul>

        <hr className="my-8 border-slate-200" />

        <h2 className="text-2xl font-bold text-slate-800 mt-8 mb-4">Governing Law</h2>
        <p className="text-slate-600 text-sm leading-relaxed mb-4">
          These terms are governed by the laws of India. Any disputes will be subject to the jurisdiction of courts in Bangalore, Karnataka.
        </p>

        <hr className="my-8 border-slate-200" />

        <h2 className="text-2xl font-bold text-slate-800 mt-8 mb-4">Changes to These Terms</h2>
        <p className="text-slate-600 text-sm leading-relaxed mb-4">
          We may update these terms. We will notify you by email at least 14 days before significant changes take effect. Continued use after that date means you accept the new terms.
        </p>

        <hr className="my-8 border-slate-200" />

        <h2 className="text-2xl font-bold text-slate-800 mt-8 mb-4">Contact</h2>
        <p className="text-slate-600 text-sm leading-relaxed mb-4">
          For any questions about these terms:
        </p>
        <p className="text-slate-600 text-sm leading-relaxed mb-1">
          <strong>Email:</strong> <a href="mailto:contact@distroos.in" className="text-indigo-600 hover:underline">contact@distroos.in</a>
        </p>
        <p className="text-slate-600 text-sm leading-relaxed mb-4">
          <strong>Response time:</strong> Within 2 business days
        </p>
      </div>
    </div>
  );
}
