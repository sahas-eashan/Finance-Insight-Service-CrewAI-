"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import SettingsForm from "../components/SettingsForm";
import Sidebar from "../components/Sidebar";
import TopBar from "../components/TopBar";

export default function SettingsPage() {
  const router = useRouter();

  return (
    <div className="chat-ui">
      <Sidebar />
      <main className="chat-main">
        <TopBar />
        <div 
          className="settings-backdrop"
          onClick={() => router.push("/")}
        >
          <div 
            className="settings-container"
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ marginBottom: '20px' }}>
              <Link 
                href="/" 
                className="back-link"
              >
                <span style={{ fontSize: '18px' }}>←</span>
                Back to Chat
              </Link>
            </div>
            <SettingsForm />
          </div>
        </div>
      </main>
    </div>
  );
}
