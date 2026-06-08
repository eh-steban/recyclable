import Link from "next/link";

export default function HomePage() {
  return (
    <main className="mx-auto max-w-2xl px-4 py-16">
      <h1 className="text-3xl font-bold">Recyclable</h1>
      <p className="mt-4 text-gray-600">
        Source-cited recycling rules. What can you actually put in the bin?
      </p>
      <div className="mt-8 flex flex-col gap-4">
        <Link
          href="/recycling/colorado/denver"
          className="text-blue-600 underline hover:text-blue-800"
        >
          Denver, CO recycling guide
        </Link>
        <Link
          href="/ask"
          className="text-blue-600 underline hover:text-blue-800"
        >
          Ask a recycling question
        </Link>
      </div>
    </main>
  );
}
