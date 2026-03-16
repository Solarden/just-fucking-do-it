# Homebrew Formula for JFDI - Just Fucking Do It
#
# To use this formula, create a Homebrew Tap repo:
#   1. Create a GitHub repo named "homebrew-jfdi" under your account
#   2. Copy this file into that repo at Formula/jfdi.rb
#   3. Users can then install with:
#        brew tap Solarden/jfdi
#        brew install jfdi
#
# Once published to PyPI, update the `url` to point to the PyPI sdist
# and update the `sha256` accordingly.

class Jfdi < Formula
  include Language::Python::Virtualenv

  desc "CLI fitness tracker that pushes you to hit daily exercise goals with Shia LaBeouf energy"
  homepage "https://github.com/Solarden/just-fucking-do-it"
  url "https://github.com/Solarden/just-fucking-do-it/archive/refs/tags/v0.1.0.tar.gz"
  # TODO: Update sha256 after creating the v0.1.0 GitHub release
  # Generate with: curl -sL <url> | shasum -a 256
  sha256 "PLACEHOLDER_UPDATE_AFTER_RELEASE"
  license "MIT"

  depends_on "python@3.13"

  resource "typer" do
    url "https://files.pythonhosted.org/packages/source/t/typer/typer-0.24.1.tar.gz"
    sha256 "PLACEHOLDER_UPDATE_WITH_ACTUAL_HASH"
  end

  resource "rich" do
    url "https://files.pythonhosted.org/packages/source/r/rich/rich-14.3.3.tar.gz"
    sha256 "PLACEHOLDER_UPDATE_WITH_ACTUAL_HASH"
  end

  resource "click" do
    url "https://files.pythonhosted.org/packages/source/c/click/click-8.3.1.tar.gz"
    sha256 "PLACEHOLDER_UPDATE_WITH_ACTUAL_HASH"
  end

  resource "shellingham" do
    url "https://files.pythonhosted.org/packages/source/s/shellingham/shellingham-1.5.4.tar.gz"
    sha256 "PLACEHOLDER_UPDATE_WITH_ACTUAL_HASH"
  end

  resource "markdown-it-py" do
    url "https://files.pythonhosted.org/packages/source/m/markdown-it-py/markdown_it_py-4.0.0.tar.gz"
    sha256 "PLACEHOLDER_UPDATE_WITH_ACTUAL_HASH"
  end

  resource "mdurl" do
    url "https://files.pythonhosted.org/packages/source/m/mdurl/mdurl-0.1.2.tar.gz"
    sha256 "PLACEHOLDER_UPDATE_WITH_ACTUAL_HASH"
  end

  resource "pygments" do
    url "https://files.pythonhosted.org/packages/source/p/pygments/pygments-2.19.2.tar.gz"
    sha256 "PLACEHOLDER_UPDATE_WITH_ACTUAL_HASH"
  end

  resource "annotated-doc" do
    url "https://files.pythonhosted.org/packages/source/a/annotated-doc/annotated_doc-0.0.4.tar.gz"
    sha256 "PLACEHOLDER_UPDATE_WITH_ACTUAL_HASH"
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "JFDI", shell_output("#{bin}/jfdi --help")
  end
end
