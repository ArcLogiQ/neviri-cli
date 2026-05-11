# Template Homebrew formula for `neviri-cli`.
#
# This file is the SOURCE OF TRUTH and is copied to the
# github.com/ArcLogiQ/homebrew-tap repository's Formula/ dir by the
# release.yml workflow on every tag push. Users install via:
#
#   brew tap ArcLogiQ/tap
#   brew install neviri
#
# The version + URLs + sha256 fields are bumped automatically by the
# tap-bump CI step — do NOT hand-edit unless you also know to refresh the
# sha256s.
class Neviri < Formula
  desc "Official command-line interface for the Neviri Cloud Platform"
  homepage "https://github.com/ArcLogiQ/neviri-cli"
  version "0.9.0b1"
  license "Apache-2.0"

  on_macos do
    on_arm do
      url "https://github.com/ArcLogiQ/neviri-cli/releases/download/v0.9.0b1/neviri-macos-arm64"
      sha256 "PLACEHOLDER_FILLED_BY_CI"
    end
    on_intel do
      url "https://github.com/ArcLogiQ/neviri-cli/releases/download/v0.9.0b1/neviri-macos-x86_64"
      sha256 "PLACEHOLDER_FILLED_BY_CI"
    end
  end

  on_linux do
    url "https://github.com/ArcLogiQ/neviri-cli/releases/download/v0.9.0b1/neviri-linux-x86_64"
    sha256 "PLACEHOLDER_FILLED_BY_CI"
  end

  def install
    if OS.mac? && Hardware::CPU.arm?
      bin.install "neviri-macos-arm64" => "neviri"
    elsif OS.mac?
      bin.install "neviri-macos-x86_64" => "neviri"
    else
      bin.install "neviri-linux-x86_64" => "neviri"
    end
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/neviri --version")
  end
end
