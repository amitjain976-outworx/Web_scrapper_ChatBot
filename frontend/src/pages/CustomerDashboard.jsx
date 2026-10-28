import { useEffect, useRef, useState } from "react";
import axios from "axios";
import { FaBars, FaPaperPlane, FaPlus, FaTimes } from "react-icons/fa";
import { useAuth } from "../AuthContext";

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL;

export default function CustomerDashboard() {
  const { token, logout } = useAuth();

  const api = axios.create({
    baseURL: API_BASE_URL,
    headers: { Authorization: `Bearer ${token}` },
  });

  const bottomRef = useRef(null);
  const textareaRef = useRef(null);

  const [crawlJobs, setCrawlJobs] = useState([]);
  const [selectedJob, setSelectedJob] = useState("");
  const [sessions, setSessions] = useState([]);
  const [activeSession, setActiveSession] = useState(null);

  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  /* -------------------- Effects -------------------- */

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    const loadInitialData = async () => {
      try {
        const [jobsRes, sessionsRes] = await Promise.all([
          api.get("/customer/crawl-jobs"),
          api.get("/customer/chat-sessions"),
        ]);

        setCrawlJobs(jobsRes.data || []);
        setSessions(sessionsRes.data || []);
      } catch (err) {
        if (err.response?.status === 401) logout();
      }
    };

    loadInitialData();
  }, []);

  /* -------------------- Helpers -------------------- */

  const loadMessages = async (sessionId) => {
    try {
      const res = await api.get(
        `/customer/chat-sessions/${sessionId}/messages`
      );
      setMessages(res.data || []);
    } catch {
      setMessages([]);
    }
  };

  const createSession = async () => {
    if (!selectedJob) {
      setError("Select a crawl job first");
      return;
    }

    try {
      const res = await api.post(
        "/customer/chat-sessions",
        null,
        { params: { crawl_job_id: selectedJob } }
      );

      setSessions((prev) => [res.data, ...prev]);
      setActiveSession(res.data);
      setMessages([]);
      setIsSidebarOpen(false);
    } catch (err) {
      setError("Failed to create chat session");
    }
  };

  /* -------------------- Send Message -------------------- */

  const handleSend = async (e) => {
    e.preventDefault();
    if (!question.trim() || !activeSession) return;

    const tempMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: question,
      pending: true,
    };

    setMessages((prev) => [...prev, tempMessage]);
    setQuestion("");
    setLoading(true);

    try {
      const res = await api.post("/customer/chat", {
        crawl_job_id: activeSession.crawl_job_id,
        session_id: activeSession.id,
        question,
        top_k: 5,
      });

      setMessages((prev) =>
        prev
          .map((m) =>
            m.id === tempMessage.id ? { ...m, pending: false } : m
          )
          .concat({
            role: "assistant",
            content: res.data.answer,
            sources: res.data.sources,
          })
      );
    } catch (err) {
      setMessages((prev) =>
        prev.concat({
          role: "assistant",
          content:
            err.response?.data?.detail ||
            "Failed to get response",
        })
      );
    } finally {
      setLoading(false);
    }
  };

  /* -------------------- UI -------------------- */

  return (
    <div className="flex h-screen bg-white">
      {/* SIDEBAR */}
      {isSidebarOpen && (
        <div
          className="fixed inset-0 bg-black/40 z-40 md:hidden"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}

      <aside
        className={`fixed md:static z-50 top-0 left-0 h-full w-72 bg-white border-r
        flex flex-col transform transition-transform duration-300
        ${isSidebarOpen ? "translate-x-0" : "-translate-x-full"}
        md:translate-x-0`}
      >
        <div className="p-4 border-b flex justify-between items-center">
          <span className="font-semibold">Chats</span>
          <button className="md:hidden" onClick={() => setIsSidebarOpen(false)}>
            <FaTimes />
          </button>
        </div>

        <div className="p-3">
          <select
            className="w-full border rounded p-2 mb-2"
            value={selectedJob}
            onChange={(e) => setSelectedJob(e.target.value)}
          >
            <option value="">Select crawl job</option>
            {crawlJobs.map((job) => (
              <option key={job.id} value={job.id}>
                {job.domain}
              </option>
            ))}
          </select>

          <button
            onClick={createSession}
            className="w-full flex items-center justify-center gap-2
            bg-blue-600 text-white py-2 rounded hover:bg-blue-700"
          >
            <FaPlus /> New Chat
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {sessions.map((s) => (
            <div
              key={s.id}
              onClick={() => {
                setActiveSession(s);
                loadMessages(s.id);
                setIsSidebarOpen(false);
              }}
              className={`p-3 rounded cursor-pointer
              ${
                activeSession?.id === s.id
                  ? "bg-gray-300"
                  : "hover:bg-gray-200"
              }`}
            >
              <p className="text-sm truncate">
                {s.title || "Chat"}
              </p>
            </div>
          ))}
        </div>

        <div className="p-3 border-t">
          <button
            onClick={logout}
            className="w-full bg-red-600 text-white py-2 rounded"
          >
            Logout
          </button>
        </div>
      </aside>

      {/* MAIN */}
      <main className="flex-1 flex flex-col overflow-hidden">
        <div className="md:hidden px-4 py-3 border-b">
          <button onClick={() => setIsSidebarOpen(true)}>
            <FaBars />
          </button>
        </div>

        {/* MESSAGES */}
        <div className="flex-1 overflow-y-auto">
          <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
            {messages.map((msg, i) => (
              <div
                key={i}
                className={`flex ${
                  msg.role === "user"
                    ? "justify-end"
                    : "justify-start"
                }`}
              >
                <div
                  className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm
                  ${
                    msg.role === "user"
                      ? "bg-blue-600 text-white"
                      : "bg-gray-100"
                  }`}
                >
                  <p className="whitespace-pre-wrap">
                    {msg.content}
                  </p>
                </div>
              </div>
            ))}

            {loading && (
              <p className="text-xs text-gray-400">
                Thinking…
              </p>
            )}
            <div ref={bottomRef} />
          </div>
        </div>

        {/* INPUT */}
        {activeSession && (
          <form
            onSubmit={handleSend}
            className="border-t bg-white p-4"
          >
            <div className="max-w-3xl mx-auto flex gap-3">
              <textarea
                ref={textareaRef}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                rows={1}
                placeholder="Ask something…"
                className="flex-1 resize-none border rounded px-3 py-2"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSend(e);
                  }
                }}
              />
              <button
                type="submit"
                disabled={loading || !question.trim()}
                className="px-4 py-2 bg-blue-600 text-white rounded"
              >
                <FaPaperPlane />
              </button>
            </div>
            {error && (
              <p className="text-red-500 text-sm mt-2 text-center">
                {error}
              </p>
            )}
          </form>
        )}
      </main>
    </div>
  );
}
