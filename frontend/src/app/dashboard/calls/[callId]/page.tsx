"use client";

import { use, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  ArrowLeft,
  Loader2,
  AlertCircle,
  Play,
  Pause,
  Download,
  Phone,
  Clock,
  User,
  Bot,
  Calendar,
  PhoneIncoming,
  PhoneOutgoing,
  FileText,
} from "lucide-react";
import { getCall, type CallRecord } from "@/lib/api/calls";

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  if (mins === 0) return `${secs} seconds`;
  return `${mins}m ${secs}s`;
}

function formatPhoneNumber(number: string): string {
  if (number.startsWith("+1") && number.length === 12) {
    return `(${number.slice(2, 5)}) ${number.slice(5, 8)}-${number.slice(8)}`;
  }
  return number;
}

function getStatusBadgeVariant(status: string) {
  switch (status) {
    case "completed":
      return "default";
    case "failed":
    case "busy":
    case "no_answer":
      return "destructive";
    case "in_progress":
      return "secondary";
    default:
      return "outline";
  }
}

export default function CallDetailPage({ params }: { params: Promise<{ callId: string }> }) {
  const { callId } = use(params);
  const router = useRouter();
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);

  const {
    data: call,
    isLoading,
    error,
  } = useQuery<CallRecord>({
    queryKey: ["call", callId],
    queryFn: () => getCall(callId),
  });

  const handlePlayRecording = () => {
    if (!call?.recording_url) {
      toast.error("No recording available for this call");
      return;
    }

    if (isPlaying && audioRef.current) {
      audioRef.current.pause();
      setIsPlaying(false);
      return;
    }

    if (audioRef.current) {
      audioRef.current.pause();
    }

    const audio = new Audio(call.recording_url);
    audioRef.current = audio;
    setIsPlaying(true);

    audio.play().catch((err: Error) => {
      toast.error(`Failed to play recording: ${err.message}`);
      setIsPlaying(false);
    });

    audio.onended = () => {
      setIsPlaying(false);
    };
  };

  const handleDownloadTranscript = () => {
    if (!call?.transcript) {
      toast.error("No transcript available for this call");
      return;
    }

    const blob = new Blob([call.transcript], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `transcript-${call.id}.txt`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    toast.success("Transcript download started");
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-16">
        <Loader2 className="mb-4 h-16 w-16 animate-spin text-muted-foreground/50" />
        <p className="text-muted-foreground">Loading call details...</p>
      </div>
    );
  }

  if (error instanceof Error) {
    return (
      <div className="flex flex-col items-center justify-center py-16">
        <AlertCircle className="mb-4 h-16 w-16 text-destructive" />
        <h3 className="mb-2 text-lg font-semibold">Failed to load call</h3>
        <p className="mb-4 max-w-sm text-center text-sm text-muted-foreground">{error.message}</p>
        <Button variant="outline" onClick={() => router.back()}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Go Back
        </Button>
      </div>
    );
  }

  if (!call) {
    return (
      <div className="flex flex-col items-center justify-center py-16">
        <AlertCircle className="mb-4 h-16 w-16 text-muted-foreground" />
        <h3 className="mb-2 text-lg font-semibold">Call not found</h3>
        <Button variant="outline" onClick={() => router.back()}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Go Back
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/dashboard/calls">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-5 w-5" />
            </Button>
          </Link>
          <div>
            <h1 className="text-xl font-semibold">Call Details</h1>
            <p className="text-sm text-muted-foreground">
              {new Date(call.started_at).toLocaleString()}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={call.direction === "inbound" ? "default" : "secondary"}>
            {call.direction === "inbound" ? (
              <PhoneIncoming className="mr-1 h-3 w-3" />
            ) : (
              <PhoneOutgoing className="mr-1 h-3 w-3" />
            )}
            {call.direction}
          </Badge>
          <Badge variant={getStatusBadgeVariant(call.status)}>
            {call.status.replace("_", " ")}
          </Badge>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Call Information */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Phone className="h-4 w-4" />
              Call Information
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-muted-foreground">From</p>
                <p className="font-mono">{formatPhoneNumber(call.from_number)}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">To</p>
                <p className="font-mono">{formatPhoneNumber(call.to_number)}</p>
              </div>
            </div>

            <Separator />

            <div className="grid grid-cols-2 gap-4">
              <div className="flex items-center gap-2">
                <Clock className="h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="text-sm text-muted-foreground">Duration</p>
                  <p className="font-medium">{formatDuration(call.duration_seconds)}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Calendar className="h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="text-sm text-muted-foreground">Started</p>
                  <p className="text-sm">{new Date(call.started_at).toLocaleString()}</p>
                </div>
              </div>
            </div>

            {call.answered_at && (
              <div className="flex items-center gap-2">
                <Calendar className="h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="text-sm text-muted-foreground">Answered</p>
                  <p className="text-sm">{new Date(call.answered_at).toLocaleString()}</p>
                </div>
              </div>
            )}

            {call.ended_at && (
              <div className="flex items-center gap-2">
                <Calendar className="h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="text-sm text-muted-foreground">Ended</p>
                  <p className="text-sm">{new Date(call.ended_at).toLocaleString()}</p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Agent & Contact */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Bot className="h-4 w-4" />
              Agent & Contact
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
                <Bot className="h-5 w-5 text-primary" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Agent</p>
                <p className="font-medium">{call.agent_name ?? "Unknown Agent"}</p>
                {call.agent_id && (
                  <Link
                    href={`/dashboard/agents/${call.agent_id}`}
                    className="text-xs text-primary hover:underline"
                  >
                    View Agent
                  </Link>
                )}
              </div>
            </div>

            <Separator />

            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-secondary">
                <User className="h-5 w-5 text-muted-foreground" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Contact</p>
                <p className="font-medium">{call.contact_name ?? "Unknown Contact"}</p>
              </div>
            </div>

            {call.workspace_name && (
              <>
                <Separator />
                <div>
                  <p className="text-sm text-muted-foreground">Workspace</p>
                  <p className="font-medium">{call.workspace_name}</p>
                </div>
              </>
            )}

            <Separator />

            <div>
              <p className="text-sm text-muted-foreground">Provider</p>
              <p className="font-medium capitalize">{call.provider}</p>
              <p className="font-mono text-xs text-muted-foreground">{call.provider_call_id}</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recording */}
      {call.recording_url && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between text-base">
              <span className="flex items-center gap-2">
                <Play className="h-4 w-4" />
                Recording
              </span>
              <Button variant="outline" size="sm" onClick={handlePlayRecording}>
                {isPlaying ? (
                  <>
                    <Pause className="mr-2 h-4 w-4" />
                    Pause
                  </>
                ) : (
                  <>
                    <Play className="mr-2 h-4 w-4" />
                    Play
                  </>
                )}
              </Button>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <audio
              src={call.recording_url}
              controls
              className="w-full"
              onPlay={() => setIsPlaying(true)}
              onPause={() => setIsPlaying(false)}
              onEnded={() => setIsPlaying(false)}
            />
          </CardContent>
        </Card>
      )}

      {/* Transcript */}
      {call.transcript && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between text-base">
              <span className="flex items-center gap-2">
                <FileText className="h-4 w-4" />
                Transcript
              </span>
              <Button variant="outline" size="sm" onClick={handleDownloadTranscript}>
                <Download className="mr-2 h-4 w-4" />
                Download
              </Button>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="max-h-96 overflow-y-auto rounded-lg bg-muted/50 p-4">
              <pre className="whitespace-pre-wrap font-sans text-sm">{call.transcript}</pre>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
