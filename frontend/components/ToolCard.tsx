import Link from "next/link";

type Props = {
  icon: string;
  title: string;
  description: string;
  /** Când e dat, apare un buton spre Repository filtrat pe acest tool. */
  tool?: string;
};

export default function ToolCard({ icon, title, description, tool }: Props) {
  return (
    <div className="flex items-center gap-3 mb-4 pb-4 border-b border-slate-100">
      <div className="w-10 h-10 bg-[#eef0f8] rounded-lg flex items-center justify-center text-xl shrink-0">
        {icon}
      </div>
      <div>
        <h2 className="font-bold text-[#1e3a5f] text-base">{title}</h2>
        <p className="text-xs text-slate-400">{description}</p>
      </div>
      {tool && (
        <Link
          href={`/repository?tool=${tool}`}
          className="ml-auto shrink-0 text-xs font-medium text-[#18257f] border border-[#c7ccf0] rounded-lg px-3 py-1.5 hover:bg-[#eef0f8] transition-colors"
        >
          Istoric
        </Link>
      )}
    </div>
  );
}
