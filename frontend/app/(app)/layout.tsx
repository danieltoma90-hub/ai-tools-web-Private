import Sidebar from "@/components/Sidebar";

export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col min-h-screen">
      <div className="ts-stripe" />
      <div className="flex flex-1">
        <Sidebar />
        <main className="flex-1 overflow-auto bg-[#f1f3f8]">{children}</main>
      </div>
      <div className="ts-stripe" />
    </div>
  );
}
