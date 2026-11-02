package com.sonik.browser;

import android.app.Activity;
import android.os.Bundle;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.view.ViewGroup;
import android.view.View;

public class SonikActivity extends Activity {
    private WebView webView;
    private EditText urlBar;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        WebView.setWebContentsDebuggingEnabled(true);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);

        LinearLayout bar = new LinearLayout(this);
        bar.setOrientation(LinearLayout.HORIZONTAL);

        urlBar = new EditText(this);
        urlBar.setHint("https://...");
        urlBar.setSingleLine(true);
        urlBar.setLayoutParams(new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

        Button goBtn = new Button(this);
        goBtn.setText("Go");
        goBtn.setLayoutParams(new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        goBtn.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) {
                String url = urlBar.getText().toString();
                if (!url.startsWith("http")) url = "https://" + url;
                webView.loadUrl(url);
            }
        });

        bar.addView(urlBar);
        bar.addView(goBtn);
        bar.setLayoutParams(new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        webView = new WebView(this);
        webView.setWebViewClient(new WebViewClient());
        webView.setLayoutParams(new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        webView.loadUrl("https://example.com");

        root.addView(bar);
        root.addView(webView);
        setContentView(root);

        startCdpBridge();
    }

    private void startCdpBridge() {
        new Thread(new Runnable() {
            @Override public void run() {
                try {
                    java.net.ServerSocket server = new java.net.ServerSocket(9222, 10, java.net.InetAddress.getByName("127.0.0.1"));
                    while (true) {
                        java.net.Socket client = server.accept();
                        new Thread(new ClientHandler(client)).start();
                    }
                } catch (Exception e) { e.printStackTrace(); }
            }
        }).start();
    }

    private class ClientHandler implements Runnable {
        private java.net.Socket client;
        ClientHandler(java.net.Socket s) { this.client = s; }
        @Override public void run() {
            try {
                android.net.LocalSocket local = new android.net.LocalSocket();
                String sockName = "webview_devtools_remote_" + android.os.Process.myPid();
                local.connect(new android.net.LocalSocketAddress(sockName, android.net.LocalSocketAddress.Namespace.ABSTRACT));
                new Thread(new Pipe(client.getInputStream(), local.getOutputStream())).start();
                new Thread(new Pipe(local.getInputStream(), client.getOutputStream())).start();
            } catch (Exception e) { e.printStackTrace(); }
        }
    }

    private static class Pipe implements Runnable {
        private java.io.InputStream in;
        private java.io.OutputStream out;
        Pipe(java.io.InputStream in, java.io.OutputStream out) { this.in = in; this.out = out; }
        @Override public void run() {
            byte[] buf = new byte[8192];
            int n;
            try {
                while ((n = in.read(buf)) != -1) { out.write(buf, 0, n); out.flush(); }
            } catch (Exception e) { /* closed */ }
        }
    }
}
