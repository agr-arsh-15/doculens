import { Link } from 'react-router-dom'

const CONTACT = 'agrawalarsh15@gmail.com'
const UPDATED = '29 October 2026'

function H({ children }) {
  return <h2 className="mt-8 font-serif text-xl font-semibold">{children}</h2>
}

function Privacy() {
  return (
    <>
      <h1 className="font-serif text-3xl font-bold tracking-tight">Privacy Policy</h1>
      <p className="mt-1 text-sm text-muted">Last updated {UPDATED}</p>
      <p className="mt-6">
        DocuLens is a student project that analyses contracts and policies for risky, hidden and missing terms. It is free while
        in testing. This policy explains what we collect, why, and how you stay in control.
      </p>

      <H>What we collect</H>
      <ul className="mt-3 list-disc space-y-2 pl-5">
        <li><b>Account details from Google:</b> your name, e-mail address and profile picture, used to sign you in and show your account.</li>
        <li><b>Documents you upload or paste</b>, the text extracted from them, and the reports DocuLens creates. Original PDF and Word files are kept so you can view them next to the report.</li>
        <li><b>Usage records:</b> when you upload, analyse, chat or export, so we can apply the daily AI limits and see overall usage. These records do not contain document text.</li>
        <li><b>Your own Groq API key</b>, only if you add one in Settings. It is stored encrypted and used only for your requests.</li>
      </ul>

      <H>How your documents are processed</H>
      <ul className="mt-3 list-disc space-y-2 pl-5">
        <li>Analysis runs on our server. When AI analysis is used, only selected clause text is sent to Groq, and e-mail addresses, phone numbers, ID and account numbers are replaced with placeholders first.</li>
        <li>We do not sell your data, show ads, or use your documents to train AI models.</li>
        <li>Your documents and reports are visible only to your account. The administrator sees aggregate statistics and a user list (name, e-mail, activity counts), not your documents or reports.</li>
      </ul>

      <H>Where data is stored</H>
      <p className="mt-3">
        Account data, documents and reports are stored with Supabase (database and private file storage). The website is served by
        Vercel and the analysis server runs on Hugging Face Spaces. AI requests go to Groq. These providers process data on our behalf.
      </p>

      <H>Cookies and local storage</H>
      <p className="mt-3">We use only what is needed to keep you signed in and remember your theme. There are no analytics or advertising trackers.</p>

      <H>Keeping and deleting data</H>
      <p className="mt-3">
        Your data is kept until you delete it. You can delete individual reports from History, or delete your whole account,
        including every document, report, stored file and saved key, from <Link to="/settings" className="underline">Settings</Link>.
      </p>

      <H>Contact</H>
      <p className="mt-3">Questions or requests about your data: <a className="underline" href={`mailto:${CONTACT}`}>{CONTACT}</a>.</p>
    </>
  )
}

function Terms() {
  return (
    <>
      <h1 className="font-serif text-3xl font-bold tracking-tight">Terms of Use</h1>
      <p className="mt-1 text-sm text-muted">Last updated {UPDATED}</p>

      <H>Not legal advice</H>
      <p className="mt-3">
        DocuLens produces automated risk analysis for information only. It can miss issues or flag terms that are acceptable in
        your situation. It is not legal advice and does not create a lawyer-client relationship. Consult a qualified
        professional before acting on any finding.
      </p>

      <H>Testing period</H>
      <p className="mt-3">
        DocuLens is free while in testing. Features, daily AI limits and availability may change, and the service may be paused
        or discontinued. The free hosting tier can take up to a minute to start after a period of inactivity.
      </p>

      <H>Your content</H>
      <p className="mt-3">
        You keep all rights to the documents you upload. You confirm that you are allowed to upload them, and you give us
        permission to store and process them only to provide the analysis to you.
      </p>

      <H>Acceptable use</H>
      <ul className="mt-3 list-disc space-y-2 pl-5">
        <li>Do not upload content you have no right to share, or malware.</li>
        <li>Do not try to access other users' data, overload the service, or get around the usage limits.</li>
        <li>Accounts that break these rules can be suspended.</li>
      </ul>

      <H>No warranty</H>
      <p className="mt-3">
        The service is provided "as is" without warranties of any kind. To the extent the law allows, we are not liable for
        decisions you make based on its output. Nothing in these terms limits rights you have under consumer law that cannot be excluded.
      </p>

      <H>Contact</H>
      <p className="mt-3"><a className="underline" href={`mailto:${CONTACT}`}>{CONTACT}</a></p>
    </>
  )
}

export default function Legal({ page }) {
  return (
    <article className="mx-auto max-w-2xl px-5 py-12 text-[15px] leading-relaxed text-ink-2">
      {page === 'privacy' ? <Privacy /> : <Terms />}
    </article>
  )
}
