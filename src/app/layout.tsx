import "./globals.css";
import './layout.css';
import { Inter } from "next/font/google";
import EnvironmentBanner from "@/components/environment-banner";

const inter = Inter({ subsets: ["latin"] });

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
	return (
		<html lang="en">
			<body className={inter.className}>
				{children}
				<EnvironmentBanner />
			</body>
		</html>
	);
}
