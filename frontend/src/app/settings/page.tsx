import { AppShell } from "@/components/app-shell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function SettingsPage() {
  return (
    <AppShell>
      <Card>
        <CardHeader>
          <CardTitle>Settings</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-[14px] text-[#3d4558]">Name</label>
              <Input defaultValue="Demo User" />
            </div>
            <div>
              <label className="mb-1 block text-[14px] text-[#3d4558]">Email</label>
              <Input defaultValue="demo@wealthsense.ai" />
            </div>
          </div>
          <div>
            <label className="mb-1 block text-[14px] text-[#3d4558]">How your money is split preference</label>
            <select className="h-11 w-full rounded-md border border-ws-border bg-ws-surface px-3 text-[14px]">
              <option>Keep things steady</option>
              <option>Balanced growth</option>
              <option>Higher growth potential</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-[14px] text-[#3d4558]">Weekly digest</label>
            <select className="h-11 w-full rounded-md border border-ws-border bg-ws-surface px-3 text-[14px]">
              <option>On</option>
              <option>Off</option>
            </select>
          </div>
        </CardContent>
      </Card>
    </AppShell>
  );
}

