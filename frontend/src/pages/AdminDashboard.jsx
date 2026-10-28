// src/pages/AdminDashboard.jsx
import React, { useEffect, useState, useCallback  } from "react";
import axios from "axios";
import { useAuth } from "../AuthContext";

const backendUrl = process.env.REACT_APP_API_BASE_URL || "http://127.0.0.1:8000";

const STATUS_COLORS = {
  pending: "bg-yellow-200 text-yellow-800",
  running: "bg-blue-200 text-blue-800",
  completed: "bg-green-200 text-green-800",
  failed: "bg-red-200 text-red-800",
  stopped: "bg-gray-200 text-gray-800",
};

export default function AdminDashboard() {
  const { token, user, logout } = useAuth();

  const [crawlJobs, setCrawlJobs] = useState([]);
  const [loadingJobs, setLoadingJobs] = useState(false);
  const [form, setForm] = useState({
    start_url: "",
    max_depth: "",
    max_pages: "",
    login_required: false,
    login_config: {
      login_url: "",
      username: "",
      password: "",
      username_selector: "",
      password_selector: "",
      submit_selector: "",
      success_check: "",
    },
  });
  const [submitting, setSubmitting] = useState(false);

  // Redirect non-admins
  useEffect(() => {
    if (!user || user.role !== "admin") {
      window.location.href = "/";
    }
  }, [user]);

  // Fetch crawl jobs
  const fetchCrawlJobs = useCallback(async () => {
    setLoadingJobs(true);
    try {
      const res = await axios.get(`${backendUrl}/admin/crawls`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setCrawlJobs(res.data);
    } catch (err) {
      console.error(err);
      alert("Failed to fetch crawl jobs");
    } finally {
      setLoadingJobs(false);
    }
  }, [token]);

  useEffect(() => {
    fetchCrawlJobs();
  }, [fetchCrawlJobs]);

  // Handle form change
  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    if (name.startsWith("login_config.")) {
      const key = name.split(".")[1];
      setForm((prev) => ({
        ...prev,
        login_config: { ...prev.login_config, [key]: value },
      }));
    } else if (type === "checkbox") {
      setForm((prev) => ({ ...prev, [name]: checked }));
    } else {
      setForm((prev) => ({ ...prev, [name]: value }));
    }
  };

  // Start Crawl
  const handleStartCrawl = async (e) => {
    e.preventDefault();
    setSubmitting(true);

    const payload = {
      start_url: form.start_url,
      max_depth: parseInt(form.max_depth),
      max_pages: form.max_pages ? parseInt(form.max_pages) : undefined,
      login_config: form.login_required ? form.login_config : undefined,
    };

    try {
      await axios.post(`${backendUrl}/admin/crawl/start`, payload, {
        headers: { Authorization: `Bearer ${token}` },
      });
      alert("Crawl started successfully!");
      setForm({
        start_url: "",
        max_depth: "",
        max_pages: "",
        login_required: false,
        login_config: {
          login_url: "",
          username: "",
          password: "",
          username_selector: "",
          password_selector: "",
          submit_selector: "",
          success_check: "",
        },
      });
      fetchCrawlJobs();
    } catch (err) {
      console.error(err);
      alert(err.response?.data?.detail || "Failed to start crawl");
    } finally {
      setSubmitting(false);
    }
  };

  // Stop Crawl
  const handleStopCrawl = async (jobId) => {
    if (!window.confirm("Are you sure you want to stop this crawl?")) return;

    try {
      await axios.post(`${backendUrl}/admin/crawl/${jobId}/stop`, {}, {
        headers: { Authorization: `Bearer ${token}` },
      });
      fetchCrawlJobs();
    } catch (err) {
      console.error(err);
      alert(err.response?.data?.detail || "Failed to stop crawl");
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold">Admin Dashboard</h1>

        <button
          onClick={logout}
          className="bg-red-600 text-white px-4 py-2 rounded hover:bg-red-700"
        >
          Logout
        </button>
      </div>

      {/* Start Crawl Form */}
      <form
        onSubmit={handleStartCrawl}
        className="bg-white p-6 rounded shadow mb-8"
      >
        <h2 className="text-xl font-semibold mb-4">Start New Crawl</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <input
            type="url"
            name="start_url"
            placeholder="Start URL"
            required
            value={form.start_url}
            onChange={handleChange}
            className="border p-2 rounded w-full"
          />
          <input
            type="number"
            name="max_depth"
            placeholder="Max Depth"
            required
            min={0}
            max={10}
            value={form.max_depth}
            onChange={handleChange}
            className="border p-2 rounded w-full"
          />
          <input
            type="number"
            name="max_pages"
            placeholder="Max Pages"
            min={1}
            value={form.max_pages}
            onChange={handleChange}
            className="border p-2 rounded w-full"
          />
          <label className="flex items-center space-x-2">
            <input
              type="checkbox"
              name="login_required"
              checked={form.login_required}
              onChange={handleChange}
            />
            <span>Site requires login</span>
          </label>
        </div>

        {/* Optional login config */}
        {form.login_required && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
            <input
              type="url"
              name="login_config.login_url"
              placeholder="Login URL"
              required
              value={form.login_config.login_url}
              onChange={handleChange}
              className="border p-2 rounded w-full"
            />
            <input
              type="text"
              name="login_config.username"
              placeholder="Username"
              required
              value={form.login_config.username}
              onChange={handleChange}
              className="border p-2 rounded w-full"
            />
            <input
              type="password"
              name="login_config.password"
              placeholder="Password"
              required
              value={form.login_config.password}
              onChange={handleChange}
              className="border p-2 rounded w-full"
            />
            <input
              type="text"
              name="login_config.username_selector"
              placeholder="Username Selector"
              required
              value={form.login_config.username_selector}
              onChange={handleChange}
              className="border p-2 rounded w-full"
            />
            <input
              type="text"
              name="login_config.password_selector"
              placeholder="Password Selector"
              required
              value={form.login_config.password_selector}
              onChange={handleChange}
              className="border p-2 rounded w-full"
            />
            <input
              type="text"
              name="login_config.submit_selector"
              placeholder="Submit Selector"
              required
              value={form.login_config.submit_selector}
              onChange={handleChange}
              className="border p-2 rounded w-full"
            />
            <input
              type="text"
              name="login_config.success_check"
              placeholder="Success Check"
              required
              value={form.login_config.success_check}
              onChange={handleChange}
              className="border p-2 rounded w-full"
            />
          </div>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="mt-4 bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
        >
          {submitting ? "Starting..." : "Start Crawl"}
        </button>
      </form>

      {/* Crawl Jobs Table */}
      <div className="bg-white p-6 rounded shadow">
        <h2 className="text-xl font-semibold mb-4">Crawl Jobs</h2>
        {loadingJobs ? (
          <p>Loading crawl jobs...</p>
        ) : crawlJobs.length === 0 ? (
          <p>No crawl jobs yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full border border-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 border">Start URL</th>
                  <th className="px-4 py-2 border">Domain</th>
                  <th className="px-4 py-2 border">Depth</th>
                  <th className="px-4 py-2 border">Max Pages</th>
                  <th className="px-4 py-2 border">Login</th>
                  <th className="px-4 py-2 border">Status</th>
                  <th className="px-4 py-2 border">Actions</th>
                </tr>
              </thead>
              <tbody>
                {crawlJobs.map((job) => (
                  <tr key={job.id} className="text-center">
                    <td className="px-4 py-2 border">{job.start_url}</td>
                    <td className="px-4 py-2 border">{job.domain}</td>
                    <td className="px-4 py-2 border">{job.max_depth}</td>
                    <td className="px-4 py-2 border">{job.max_pages || "-"}</td>
                    <td className="px-4 py-2 border">{job.has_login ? "Yes" : "No"}</td>
                    <td className="px-4 py-2 border">
                      <span
                        className={`px-2 py-1 rounded text-sm font-semibold ${STATUS_COLORS[job.status]}`}
                      >
                        {job.status}
                      </span>
                    </td>
                    <td className="px-4 py-2 border space-x-2">
                      {(job.status === "pending" || job.status === "running") && (
                        <button
                          onClick={() => handleStopCrawl(job.id)}
                          className="bg-red-600 text-white px-2 py-1 rounded hover:bg-red-700"
                        >
                          Stop
                        </button>
                      )}
                      <button
                        onClick={fetchCrawlJobs}
                        className="bg-gray-600 text-white px-2 py-1 rounded hover:bg-gray-700"
                      >
                        Refresh
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
