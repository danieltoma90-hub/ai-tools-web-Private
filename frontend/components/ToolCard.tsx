type Props = { icon: string; title: string; description: string };

export default function ToolCard({ icon, title, description }: Props) {
  return (
    <div className="flex items-center gap-3 mb-4 pb-4 border-b border-slate-100">
      <div className="w-10 h-10 bg-blue-50 rounded-lg flex items-center justify-center text-xl shrink-0">
        {icon}
      </div>
      <div>
        <h2 className="font-bold text-[#1e3a5f] text-base">{title}</h2>
        <p className="text-xs text-slate-400">{description}</p>
      </div>
    </div>
  );
}
