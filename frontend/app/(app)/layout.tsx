import Sidebar from "@/components/Sidebar";
import AccesGuard from "@/components/AccesGuard";

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
        <main className="flex-1 overflow-auto bg-[#f1f3f8]">
          <AccesGuard>{children}</AccesGuard>
        </main>
      </div>
      <div className="ts-stripe" />
    </div>
  );
}
