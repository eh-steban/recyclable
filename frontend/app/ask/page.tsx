import { AskBox } from "@/components/ask-box/ask-box";

export default function AskPage() {
  return (
    <main className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="text-2xl font-bold text-gray-900">Recycling Assistant</h1>
      <p className="mt-2 text-gray-600">
        Ask a recycling question for your city.
      </p>
      <div className="mt-8">
        <AskBox />
      </div>
    </main>
  );
}
